#!/usr/bin/env python3
"""Tests for scripts/validation/validate_reference.py (PHASE 1.1).

The validator is the gate that decides what becomes the character's source of
truth, so its failure modes are tested rather than assumed.

Run:
    python3 -m unittest discover -s tests -p 'test_*.py' -v
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "validation" / "validate_reference.py"

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover - environment without Pillow
    Image = None


def make_reference(path, size=(1024, 1024), mode="RGBA", opaque_background=False):
    """A minimal stand-in for a character cutout: an opaque blob on transparent."""
    background = (255, 255, 255, 255) if opaque_background else (0, 0, 0, 0)
    image = Image.new(mode, size, background if mode == "RGBA" else (255, 255, 255))
    draw = ImageDraw.Draw(image)
    width, height = size
    draw.ellipse([width * 0.3, height * 0.2, width * 0.7, height * 0.8],
                 fill=(230, 200, 180, 255))
    image.save(path)
    return path


@unittest.skipIf(Image is None, "Pillow is required for these tests")
class ValidateReferenceTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.fake_repo = self.tmp / "repo"
        (self.fake_repo / "character" / "reference").mkdir(parents=True)
        (self.fake_repo / "metadata" / "generations").mkdir(parents=True)
        self.addCleanup(self._tmp.cleanup)

    def run_validator(self, *args):
        env = dict(os.environ, NARRA_REPO=str(self.fake_repo))
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              capture_output=True, text=True, env=env)

    # --- validation ------------------------------------------------------

    def test_conforming_image_passes(self):
        candidate = make_reference(self.tmp / "good.png")
        result = self.run_validator(str(candidate))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Automated checks passed", result.stdout)

    def test_wrong_resolution_fails(self):
        candidate = make_reference(self.tmp / "small.png", size=(512, 512))
        result = self.run_validator(str(candidate))
        self.assertEqual(result.returncode, 1)
        self.assertIn("[FAIL] resolution", result.stdout)

    def test_non_square_fails(self):
        candidate = make_reference(self.tmp / "wide.png", size=(1024, 768))
        result = self.run_validator(str(candidate))
        self.assertEqual(result.returncode, 1)
        self.assertIn("aspect-ratio", result.stdout)

    def test_rgb_without_alpha_fails(self):
        candidate = make_reference(self.tmp / "rgb.png", mode="RGB")
        result = self.run_validator(str(candidate))
        self.assertEqual(result.returncode, 1)
        self.assertIn("[FAIL] color-mode", result.stdout)

    def test_opaque_background_fails(self):
        candidate = make_reference(self.tmp / "flat.png", opaque_background=True)
        result = self.run_validator(str(candidate))
        self.assertEqual(result.returncode, 1)
        self.assertIn("alpha/background", result.stdout)

    def test_empty_cutout_fails(self):
        candidate = self.tmp / "empty.png"
        Image.new("RGBA", (1024, 1024), (0, 0, 0, 0)).save(candidate)
        result = self.run_validator(str(candidate))
        self.assertEqual(result.returncode, 1)
        self.assertIn("alpha/coverage", result.stdout)

    def test_non_png_fails(self):
        candidate = self.tmp / "fake.png"
        candidate.write_bytes(b"this is not a png")
        result = self.run_validator(str(candidate))
        self.assertEqual(result.returncode, 1)
        self.assertIn("[FAIL] format/png", result.stdout)

    def test_missing_file_is_usage_error(self):
        result = self.run_validator(str(self.tmp / "nope.png"))
        self.assertEqual(result.returncode, 2)

    # --- import ----------------------------------------------------------

    def test_import_writes_master_alias_and_sidecars(self):
        candidate = make_reference(self.tmp / "good.png")
        result = self.run_validator(str(candidate), "--import")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        reference_dir = self.fake_repo / "character" / "reference"
        master = reference_dir / "narra-reference-master-v1.png"
        alias = reference_dir / "master.png"
        sidecar = reference_dir / "narra-reference-master-v1.json"
        mirror = self.fake_repo / "metadata" / "generations" / "narra-reference-master-v1.json"

        for target in (master, alias, sidecar, mirror):
            self.assertTrue(target.exists(), f"{target} was not written")

        self.assertEqual(master.read_bytes(), alias.read_bytes(),
                         "master.png must be byte-identical to the versioned master")
        self.assertEqual(sidecar.read_text(), mirror.read_text())

    def test_import_sidecar_has_mandatory_fields(self):
        candidate = make_reference(self.tmp / "good.png")
        self.run_validator(str(candidate), "--import")
        sidecar = json.loads(
            (self.fake_repo / "character" / "reference" / "narra-reference-master-v1.json").read_text())

        # ASSET_SPEC.md section 11
        self.assertEqual(sidecar["character"], "narra")
        self.assertEqual(sidecar["asset_type"], "reference")
        self.assertEqual(sidecar["asset_name"], "master")
        self.assertEqual(sidecar["version"], 1)
        self.assertEqual(sidecar["generation"]["resolution"], [1024, 1024])
        self.assertEqual(sidecar["validation"]["status"], "imported")
        self.assertTrue(sidecar["validation"]["validated_at"])
        self.assertEqual(len(sidecar["sha256"]), 64)

    def test_failed_candidate_is_not_imported(self):
        candidate = make_reference(self.tmp / "small.png", size=(512, 512))
        result = self.run_validator(str(candidate), "--import")
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.fake_repo / "character" / "reference"
                          / "narra-reference-master-v1.png").exists())

    # --- check-imported --------------------------------------------------

    def test_check_imported_fails_before_import(self):
        result = self.run_validator("--check-imported")
        self.assertEqual(result.returncode, 1)
        self.assertIn("imported/master", result.stdout)

    def test_check_imported_passes_after_import(self):
        candidate = make_reference(self.tmp / "good.png")
        self.run_validator(str(candidate), "--import")
        result = self.run_validator("--check-imported")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_check_imported_detects_alias_drift(self):
        candidate = make_reference(self.tmp / "good.png")
        self.run_validator(str(candidate), "--import")
        make_reference(self.fake_repo / "character" / "reference" / "master.png",
                       size=(1024, 1024))
        # rewrite the alias with a different encoding of the same subject
        alias = self.fake_repo / "character" / "reference" / "master.png"
        image = Image.open(alias)
        ImageDraw.Draw(image).rectangle([0, 0, 50, 50], fill=(1, 2, 3, 255))
        image.save(alias)

        result = self.run_validator("--check-imported")
        self.assertEqual(result.returncode, 1)
        self.assertIn("byte-identical", result.stdout)

    def test_check_imported_detects_swapped_master(self):
        candidate = make_reference(self.tmp / "good.png")
        self.run_validator(str(candidate), "--import")

        reference_dir = self.fake_repo / "character" / "reference"
        swapped = make_reference(self.tmp / "other.png")
        image = Image.open(swapped)
        ImageDraw.Draw(image).rectangle([100, 100, 200, 200], fill=(9, 9, 9, 255))
        image.save(reference_dir / "narra-reference-master-v1.png")
        (reference_dir / "master.png").write_bytes(
            (reference_dir / "narra-reference-master-v1.png").read_bytes())

        result = self.run_validator("--check-imported")
        self.assertEqual(result.returncode, 1)
        self.assertIn("sha256", result.stdout)


if __name__ == "__main__":
    unittest.main()
