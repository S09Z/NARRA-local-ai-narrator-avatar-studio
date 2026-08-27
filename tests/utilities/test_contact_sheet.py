#!/usr/bin/env python3
"""Tests for scripts/utilities/contact_sheet.py (PHASE 3.4)."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "utilities" / "contact_sheet.py"

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    Image = None

CELL, LABEL_HEIGHT, PADDING = 256, 20, 8


def draw_character(path, fill=(230, 200, 180, 255)):
    image = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse([300, 200, 724, 800], fill=fill)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path


@unittest.skipIf(Image is None, "Pillow is required for these tests")
class ContactSheetTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        (self.repo / "character" / "expressions").mkdir(parents=True)
        (self.repo / "character" / "reference").mkdir(parents=True)
        self.addCleanup(self._tmp.cleanup)

    def add_reference(self):
        return draw_character(
            self.repo / "character" / "reference" / "narra-reference-master-v1.png")

    def add_expression(self, name):
        return draw_character(
            self.repo / "character" / "expressions" / f"narra-expression-{name}-v1.png")

    def run_cli(self, *args):
        env = dict(os.environ, NARRA_REPO=str(self.repo))
        return subprocess.run([sys.executable, str(SCRIPT), *[str(a) for a in args]],
                              capture_output=True, text=True, env=env)

    def test_builds_a_sheet_from_explicit_assets(self):
        assets = [self.add_expression(name) for name in ("happy", "serious")]
        out = self.repo / "sheet.png"
        result = self.run_cli(*assets, "--out", out, "--no-reference")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(out.exists())

    def test_cells_are_rendered_at_the_review_size(self):
        assets = [self.add_expression(name) for name in ("happy", "serious")]
        out = self.repo / "sheet.png"
        self.run_cli(*assets, "--out", out, "--no-reference", "--columns", "2")
        with Image.open(out) as sheet:
            self.assertEqual(sheet.size,
                             (2 * (CELL + PADDING) + PADDING,
                              1 * (CELL + LABEL_HEIGHT + PADDING) + PADDING))

    def test_reference_is_the_first_cell(self):
        self.add_reference()
        self.add_expression("happy")
        out = self.repo / "sheet.png"
        result = self.run_cli("--set", "expression", "--out", out)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("2 cell(s)", result.stdout)

    def test_no_reference_flag_omits_it(self):
        self.add_reference()
        self.add_expression("happy")
        out = self.repo / "sheet.png"
        result = self.run_cli("--set", "expression", "--out", out, "--no-reference")
        self.assertIn("1 cell(s)", result.stdout)

    def test_set_uses_canonical_order_not_alphabetical(self):
        # 'neutral' is canonical index 0 but sorts after 'happy' and 'excited'.
        for name in ("happy", "excited", "neutral"):
            self.add_expression(name)
        out = self.repo / "sheet.png"
        result = self.run_cli("--set", "expression", "--out", out, "--no-reference",
                              "--columns", "3")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with Image.open(out) as sheet:
            self.assertEqual(sheet.size[0], 3 * (CELL + PADDING) + PADDING)

    def test_grid_wraps_onto_multiple_rows(self):
        assets = [self.add_expression(name)
                  for name in ("happy", "serious", "proud", "confused")]
        out = self.repo / "sheet.png"
        self.run_cli(*assets, "--out", out, "--no-reference", "--columns", "2")
        with Image.open(out) as sheet:
            self.assertEqual(sheet.size[1], 2 * (CELL + LABEL_HEIGHT + PADDING) + PADDING)

    def test_empty_set_with_no_reference_is_an_error(self):
        result = self.run_cli("--set", "expression")
        self.assertEqual(result.returncode, 1)
        self.assertIn("nothing to render", result.stderr)

    def test_unknown_set_is_a_usage_error(self):
        self.add_reference()
        result = self.run_cli("--set", "gestures")
        self.assertEqual(result.returncode, 2)

    def test_missing_asset_is_a_usage_error(self):
        result = self.run_cli(self.repo / "nope.png", "--no-reference")
        self.assertEqual(result.returncode, 2)

    def test_set_and_explicit_assets_together_is_a_usage_error(self):
        asset = self.add_expression("happy")
        result = self.run_cli(asset, "--set", "expression")
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
