#!/usr/bin/env python3
"""Tests for scripts/utilities/prep_reference.py (PHASE 1.1).

The tool edits the image that becomes the source of truth for all 38 library assets,
so what it refuses matters more than what it fixes. Each test builds a candidate with
exactly one property and checks that the property is either corrected or refused -
never quietly flattened into a pass.

Run:
    python3 -m unittest discover -s tests -p 'test_*.py' -v
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "utilities" / "prep_reference.py"
VALIDATE = REPO / "scripts" / "validation" / "validate_reference.py"

sys.path.insert(0, str(REPO / "scripts" / "lib"))
import imagecheck                                     # noqa: E402

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    Image = None

SOURCE = 1254          # the real candidate's size - not the 1024 target
BLOB = (300, 200, 950, 1050)


@unittest.skipIf(Image is None, "Pillow is required for these tests")
class PrepReferenceTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    # --- fixtures ---------------------------------------------------------

    def candidate(self, name="candidate.png", size=(SOURCE, SOURCE), alpha=253,
                  background=(0, 0, 0, 0), fill=(230, 200, 180)):
        """A blob at `alpha` on a transparent field - a clean cutout, near-opaque."""
        image = Image.new("RGBA", size, background)
        box = [BLOB[0] * size[0] // SOURCE, BLOB[1] * size[1] // SOURCE,
               BLOB[2] * size[0] // SOURCE, BLOB[3] * size[1] // SOURCE]
        ImageDraw.Draw(image).ellipse(box, fill=fill + (alpha,))
        path = self.dir / name
        image.save(path)
        return path

    def soft_matte_candidate(self, name="soft.png"):
        """Alpha ramping across the frame - a genuine matte, not an encode artefact."""
        image = Image.new("RGBA", (SOURCE, SOURCE), (0, 0, 0, 0))
        pixels = image.load()
        for y in range(SOURCE):
            value = 6 + int((y / SOURCE) * 240)       # stays inside the snap window
            for x in range(300, 950):
                pixels[x, y] = (230, 200, 180, value)
        path = self.dir / name
        image.save(path)
        return path

    # --- helpers ----------------------------------------------------------

    def prep(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *[str(a) for a in args]],
                              capture_output=True, text=True,
                              env=dict(os.environ, NARRA_REPO=str(REPO)))

    def profile(self, path):
        with Image.open(path) as image:
            alpha = image.getchannel("A")
            histogram = alpha.histogram()
            total = float(alpha.size[0] * alpha.size[1])
        return {"semi": (total - histogram[0] - histogram[255]) / total,
                "opaque": histogram[255] / total}

    # --- what it corrects -------------------------------------------------

    def test_snapped_output_passes_the_reference_validator(self):
        source = self.candidate()
        self.assertGreater(self.profile(source)["semi"], 0.20)

        out = self.dir / "out.png"
        result = self.prep(source, "--out", out)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        checked = subprocess.run([sys.executable, str(VALIDATE), str(out)],
                                 capture_output=True, text=True,
                                 env=dict(os.environ, NARRA_REPO=str(REPO)))
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        self.assertIn("Automated checks passed", checked.stdout)

    def test_resizes_to_the_required_size(self):
        out = self.dir / "out.png"
        self.assertEqual(self.prep(self.candidate(), "--out", out).returncode, 0)
        with Image.open(out) as image:
            self.assertEqual(image.size, tuple(imagecheck.REQUIRED_SIZE))

    def test_semi_transparency_collapses_to_the_antialiased_edge(self):
        out = self.dir / "out.png"
        self.prep(self.candidate(), "--out", out)
        after = self.profile(out)
        self.assertLess(after["semi"], imagecheck.MAX_SEMI_TRANSPARENT_FRACTION)
        self.assertGreater(after["opaque"], imagecheck.MIN_OPAQUE_FRACTION)

    def test_writes_beside_the_candidate_by_default(self):
        source = self.candidate()
        self.assertEqual(self.prep(source).returncode, 0)
        self.assertTrue((self.dir / "candidate-prepped.png").exists())

    def test_is_idempotent(self):
        first, second = self.dir / "first.png", self.dir / "second.png"
        self.prep(self.candidate(), "--out", first)
        self.assertEqual(self.prep(first, "--out", second).returncode, 0)
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_does_not_bleed_transparent_colour_into_the_edge(self):
        """Pins Pillow's alpha-weighted resampling, which the resize step relies on.

        Pillow weights RGB by alpha internally (verified on 10.0 and 12.3), so the
        colour of fully transparent pixels stays out of the silhouette edge. That is
        a property of the library, not of this script, which is exactly why it is
        worth a test - if a future Pillow resampled channels independently, every
        prepared reference would gain the halo ASSET_SPEC 4 exists to catch.
        """
        source = self.candidate(background=(0, 255, 0, 0), fill=(255, 0, 0))
        out = self.dir / "out.png"
        self.assertEqual(self.prep(source, "--out", out).returncode, 0)

        with Image.open(out) as image:
            pixels = image.load()
            edge_green = [pixels[x, y][1]
                          for y in range(0, image.size[1], 3)
                          for x in range(0, image.size[0], 3)
                          if 0 < pixels[x, y][3] < 255]
        self.assertTrue(edge_green, "no antialiased edge pixels to inspect")
        self.assertLess(max(edge_green), 60,
                        "green from the fully transparent field reached the silhouette")

    def test_keeps_the_silhouette_where_it_was(self):
        source = self.candidate()
        out = self.dir / "out.png"
        self.prep(source, "--out", out)
        before = imagecheck.silhouette_bbox(source)
        after = imagecheck.silhouette_bbox(out)
        for edge in ("left", "top", "right", "bottom"):
            self.assertAlmostEqual(before[edge], after[edge], delta=0.01)

    # --- what it refuses --------------------------------------------------

    def test_refuses_a_genuine_soft_matte(self):
        result = self.prep(self.soft_matte_candidate(), "--out", self.dir / "out.png")
        self.assertEqual(result.returncode, 1)
        self.assertIn("soft matte", result.stdout)
        self.assertIn("REFUSED", result.stdout)
        self.assertFalse((self.dir / "out.png").exists())

    def test_refuses_a_non_square_candidate_and_names_the_option(self):
        source = self.candidate(size=(SOURCE, 900))
        result = self.prep(source, "--out", self.dir / "out.png")
        self.assertEqual(result.returncode, 1)
        self.assertIn("--pad", result.stdout)
        self.assertFalse((self.dir / "out.png").exists())

    def test_pad_letterboxes_instead_of_squashing(self):
        source = self.candidate(size=(SOURCE, 900))
        out = self.dir / "out.png"
        self.assertEqual(self.prep(source, "--out", out, "--pad").returncode, 0)

        before = imagecheck.silhouette_bbox(source)
        after = imagecheck.silhouette_bbox(out)
        before_ratio = ((before["right"] - before["left"]) * SOURCE) / \
                       ((before["bottom"] - before["top"]) * 900)
        after_ratio = (after["right"] - after["left"]) / (after["bottom"] - after["top"])
        self.assertAlmostEqual(before_ratio, after_ratio, delta=0.02)

    def test_refuses_an_image_with_no_alpha_channel(self):
        path = self.dir / "flat.png"
        Image.new("RGB", (SOURCE, SOURCE), (120, 120, 120)).save(path)
        result = self.prep(path, "--out", self.dir / "out.png")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no cutout", result.stdout)

    def test_refuses_to_overwrite_the_candidate(self):
        source = self.candidate()
        result = self.prep(source, "--out", source)
        self.assertEqual(result.returncode, 2)
        self.assertIn("refusing to overwrite", result.stderr)

    def test_refuses_an_existing_output_until_forced(self):
        source = self.candidate()
        out = self.dir / "out.png"
        out.write_bytes(b"not an image")
        self.assertEqual(self.prep(source, "--out", out).returncode, 2)
        self.assertEqual(out.read_bytes(), b"not an image")
        self.assertEqual(self.prep(source, "--out", out, "--force").returncode, 0)

    def test_missing_candidate_is_a_usage_error(self):
        result = self.prep(self.dir / "nope.png")
        self.assertEqual(result.returncode, 2)
        self.assertIn("not found", result.stderr)


if __name__ == "__main__":
    unittest.main()
