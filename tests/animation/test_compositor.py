#!/usr/bin/env python3
"""Tests for scripts/lib/compositor.py (PHASE 8).

The image library does not exist, so these build synthetic assets with known pixel
values and composite those. That is enough to verify the thing worth verifying: that
compositing a viseme onto an expression changes the mouth region and nothing else, which
is the layering contract ADR-004 rests on and the reason 12 expressions and 16 visemes
can cover 192 combinations.

It does not verify that the real assets look right. Nothing can, until they exist.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "lib"))
import canon                          # noqa: E402
import compositor as compositor_lib   # noqa: E402

try:
    from PIL import Image
    HAVE_PILLOW = True
except ImportError:                    # pragma: no cover
    HAVE_PILLOW = False

SIZE = (1024, 1024)
# A deliberately asymmetric box, like the real one - visual-spec.md section 4 says the
# region is much taller below the anchor than above it.
REGION = {"left": 0.35, "top": 0.56, "right": 0.65, "bottom": 0.78}

FACE = (200, 170, 150, 255)
MOUTHS = {"REST": (100, 40, 40, 255), "A": (200, 0, 0, 255), "MBP": (0, 0, 200, 255)}


@unittest.skipUnless(HAVE_PILLOW, "Pillow is required to composite")
class CompositorTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

        anchor = self.repo / "character" / "bible" / "mouth-anchor.json"
        anchor.parent.mkdir(parents=True)
        anchor.write_text(json.dumps({
            "character": "narra", "status": "measured", "version": 1,
            "coordinate_space": {"normalized": True, "reference_resolution": [1024, 1024]},
            "anchor": {"anchor_x": 0.5, "anchor_y": 0.64,
                       "mouth_width": 0.18, "mouth_height": 0.06},
            "edit_region": REGION,
        }), encoding="utf-8")

        self.box = compositor_lib.edit_box(
            json.loads(anchor.read_text(encoding="utf-8")))

        expressions = self.repo / "character" / "expressions"
        visemes = self.repo / "character" / "visemes"
        expressions.mkdir(parents=True)
        visemes.mkdir(parents=True)

        for name in ("neutral", "happy"):
            self._write(expressions / canon.asset_filename("expression", name),
                        FACE, MOUTHS["REST"])
        for name, colour in MOUTHS.items():
            self._write(visemes / canon.asset_filename("viseme", name), FACE, colour)

        self.renderer = compositor_lib.FrameRenderer(self.repo)

    def _write(self, path, face, mouth):
        image = Image.new("RGBA", SIZE, face)
        image.paste(Image.new("RGBA", (self.box[2] - self.box[0],
                                       self.box[3] - self.box[1]), mouth), self.box)
        image.save(path)

    # --- the layering contract --------------------------------------------------------

    def test_a_single_viseme_lands_in_the_mouth_region(self):
        frame = self.renderer.render("neutral", [{"viseme": "A", "weight": 1.0}])
        centre = ((self.box[0] + self.box[2]) // 2, (self.box[1] + self.box[3]) // 2)
        self.assertEqual(frame.getpixel(centre), MOUTHS["A"])

    def test_nothing_outside_the_edit_region_changes(self):
        """ADR-004 and ASSET_SPEC section 7 - a viseme differs from REST only inside
        the permitted region. If that fails, the layers cannot be independent."""
        base = self.renderer.expression("neutral")
        frame = self.renderer.render("neutral", [{"viseme": "MBP", "weight": 1.0}])
        for point in [(10, 10), (512, 100), (1013, 1013), (512, 1000),
                      (self.box[0] - 5, self.box[1] - 5),
                      (self.box[2] + 5, self.box[3] + 5)]:
            with self.subTest(point=point):
                self.assertEqual(frame.getpixel(point), base.getpixel(point))

    def test_the_expression_underneath_is_preserved(self):
        for expression in ("neutral", "happy"):
            frame = self.renderer.render(expression, [{"viseme": "A", "weight": 1.0}])
            self.assertEqual(frame.getpixel((5, 5)), FACE)

    # --- blending ----------------------------------------------------------------------

    def test_an_even_blend_is_the_average_of_two_shapes(self):
        frame = self.renderer.render("neutral", [
            {"viseme": "A", "weight": 0.5}, {"viseme": "MBP", "weight": 0.5}])
        centre = ((self.box[0] + self.box[2]) // 2, (self.box[1] + self.box[3]) // 2)
        red, green, blue, alpha = frame.getpixel(centre)
        self.assertAlmostEqual(red, 100, delta=1)
        self.assertAlmostEqual(blue, 100, delta=1)
        self.assertEqual(green, 0)
        self.assertEqual(alpha, 255)

    def test_blend_weight_shifts_the_result_proportionally(self):
        frame = self.renderer.render("neutral", [
            {"viseme": "A", "weight": 0.75}, {"viseme": "MBP", "weight": 0.25}])
        centre = ((self.box[0] + self.box[2]) // 2, (self.box[1] + self.box[3]) // 2)
        red, _, blue, _ = frame.getpixel(centre)
        self.assertAlmostEqual(red, 150, delta=2)
        self.assertAlmostEqual(blue, 50, delta=2)

    def test_blend_order_does_not_matter(self):
        first = self.renderer.render("neutral", [
            {"viseme": "A", "weight": 0.3}, {"viseme": "MBP", "weight": 0.7}])
        second = self.renderer.render("neutral", [
            {"viseme": "MBP", "weight": 0.7}, {"viseme": "A", "weight": 0.3}])
        centre = ((self.box[0] + self.box[2]) // 2, (self.box[1] + self.box[3]) // 2)
        for a, b in zip(first.getpixel(centre), second.getpixel(centre)):
            self.assertAlmostEqual(a, b, delta=2)

    def test_no_layers_renders_the_bare_expression(self):
        frame = self.renderer.render("neutral", [])
        self.assertEqual(frame.tobytes(),
                         self.renderer.expression("neutral").tobytes())

    # --- refusals ----------------------------------------------------------------------

    def test_a_missing_asset_is_reported_not_guessed(self):
        with self.assertRaises(compositor_lib.CompositorError):
            self.renderer.mouth("SH")

    def test_a_wrong_sized_asset_is_rejected(self):
        path = (self.repo / "character" / "visemes"
                / canon.asset_filename("viseme", "S"))
        Image.new("RGBA", (512, 512), FACE).save(path)
        with self.assertRaises(compositor_lib.CompositorError) as caught:
            self.renderer.mouth("S")
        self.assertIn("512x512", str(caught.exception))

    def test_required_assets_lists_what_is_missing(self):
        plan = {"tracks": {"expression": [{"start": 0, "end": 1, "expression": "neutral"}],
                           "mouth": [{"layers": [{"viseme": "A", "weight": 1.0},
                                                 {"viseme": "SH", "weight": 0.0}]}]}}
        _, visemes, missing = self.renderer.required_assets(plan)
        self.assertIn("SH", visemes)
        self.assertEqual(len(missing), 1)
        self.assertIn("sh", missing[0])


class AnchorTest(unittest.TestCase):
    """PHASE 4.3 - without a measured anchor there is no edit region."""

    def test_an_unmeasured_anchor_refuses_with_the_fix(self):
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "character" / "bible" / "mouth-anchor.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"status": "unmeasured", "edit_region": None}),
                            encoding="utf-8")
            with self.assertRaises(compositor_lib.CompositorError) as caught:
                compositor_lib.load_anchor(Path(work))
            self.assertIn("measure_anchor.py", str(caught.exception))

    def test_the_real_repository_anchor_is_still_unmeasured(self):
        """A guard: if this ever passes, PHASE 4.3 happened and rendering is live."""
        with self.assertRaises(compositor_lib.CompositorError):
            compositor_lib.load_anchor(REPO)

    def test_an_inverted_region_is_rejected(self):
        with self.assertRaises(compositor_lib.CompositorError):
            compositor_lib.edit_box({"edit_region": {"left": 0.7, "top": 0.5,
                                                     "right": 0.3, "bottom": 0.8}})


if __name__ == "__main__":
    unittest.main()
