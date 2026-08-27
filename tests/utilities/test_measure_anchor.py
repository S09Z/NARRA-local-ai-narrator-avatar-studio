#!/usr/bin/env python3
"""Tests for scripts/utilities/measure_anchor.py (PHASE 4.3).

The anchor is measured once and every one of the 16 visemes is then held to it,
so a bad measurement is expensive. The plausibility guards are the point.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "utilities" / "measure_anchor.py"

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    Image = None

UNMEASURED = {
    "character": "narra",
    "status": "unmeasured",
    "anchor": {"anchor_x": None, "anchor_y": None,
               "mouth_width": None, "mouth_height": None},
    "edit_region": None,
}


class MeasureAnchorTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        (self.repo / "character" / "bible").mkdir(parents=True)
        (self.repo / "character" / "reference").mkdir(parents=True)
        self.anchor_file = self.repo / "character" / "bible" / "mouth-anchor.json"
        self.anchor_file.write_text(json.dumps(UNMEASURED, indent=2))
        self.addCleanup(self._tmp.cleanup)

    def run_cli(self, *args):
        env = dict(os.environ, NARRA_REPO=str(self.repo))
        return subprocess.run([sys.executable, str(SCRIPT), *[str(a) for a in args]],
                              capture_output=True, text=True, env=env)

    def anchor(self):
        return json.loads(self.anchor_file.read_text())

    # --- show ------------------------------------------------------------

    def test_show_reports_unmeasured(self):
        result = self.run_cli("--show")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("unmeasured", result.stdout)

    def test_show_after_measuring(self):
        self.run_cli("--box", 442, 630, 582, 700)
        result = self.run_cli("--show")
        self.assertIn("measured", result.stdout)
        self.assertIn("anchor_x", result.stdout)

    # --- measuring -------------------------------------------------------

    def test_box_is_normalized_to_the_canvas(self):
        result = self.run_cli("--box", 442, 630, 582, 700)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        anchor = self.anchor()["anchor"]
        self.assertAlmostEqual(anchor["anchor_x"], 0.500, places=3)
        self.assertAlmostEqual(anchor["anchor_y"], 0.649, places=3)  # 665/1024
        self.assertAlmostEqual(anchor["mouth_width"], 0.137, places=3)
        self.assertAlmostEqual(anchor["mouth_height"], 0.068, places=3)

    def test_status_becomes_measured(self):
        self.run_cli("--box", 442, 630, 582, 700)
        self.assertEqual(self.anchor()["status"], "measured")
        self.assertTrue(self.anchor()["measured_at"])

    def test_edit_region_is_taller_below_the_anchor(self):
        # A viseme opens the jaw downward - A needs room below the lip line.
        self.run_cli("--box", 442, 630, 582, 700)
        doc = self.anchor()
        region, anchor = doc["edit_region"], doc["anchor"]
        above = anchor["anchor_y"] - region["top"]
        below = region["bottom"] - anchor["anchor_y"]
        self.assertGreater(below, above * 2)

    def test_edit_region_contains_the_mouth(self):
        self.run_cli("--box", 442, 630, 582, 700)
        doc = self.anchor()
        region, anchor = doc["edit_region"], doc["anchor"]
        self.assertLess(region["left"], anchor["anchor_x"] - anchor["mouth_width"] / 2)
        self.assertGreater(region["right"], anchor["anchor_x"] + anchor["mouth_width"] / 2)

    def test_explicit_edit_region_is_used(self):
        result = self.run_cli("--box", 442, 630, 582, 700,
                              "--edit-region", 400, 600, 630, 780)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        region = self.anchor()["edit_region"]
        self.assertAlmostEqual(region["left"], 400 / 1024, places=3)
        self.assertAlmostEqual(region["bottom"], 780 / 1024, places=3)

    def test_edit_region_not_containing_the_mouth_is_rejected(self):
        result = self.run_cli("--box", 442, 630, 582, 700,
                              "--edit-region", 460, 640, 500, 660)
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not contain the mouth box", result.stderr)
        self.assertEqual(self.anchor()["status"], "unmeasured")

    # --- plausibility guards ---------------------------------------------

    def test_implausibly_wide_mouth_is_rejected(self):
        result = self.run_cli("--box", 100, 630, 900, 700)
        self.assertEqual(result.returncode, 1)
        self.assertIn("mouth_width", result.stderr)
        self.assertEqual(self.anchor()["status"], "unmeasured")

    def test_implausibly_tall_mouth_is_rejected(self):
        result = self.run_cli("--box", 442, 300, 582, 700)
        self.assertEqual(result.returncode, 1)
        self.assertIn("mouth_height", result.stderr)

    def test_mouth_in_the_upper_half_is_rejected_as_the_eye_line(self):
        result = self.run_cli("--box", 442, 380, 582, 440)
        self.assertEqual(result.returncode, 1)
        self.assertIn("eye line", result.stderr)

    def test_inverted_box_is_a_usage_error(self):
        result = self.run_cli("--box", 582, 700, 442, 630)
        self.assertEqual(result.returncode, 2)

    def test_a_rejected_measurement_writes_nothing(self):
        before = self.anchor_file.read_text()
        self.run_cli("--box", 100, 630, 900, 700)
        self.assertEqual(self.anchor_file.read_text(), before)

    # --- from-diff -------------------------------------------------------

    @unittest.skipIf(Image is None, "Pillow is required")
    def test_from_diff_reports_the_changed_region(self):
        reference = self.repo / "ref.png"
        asset = self.repo / "asset.png"
        base = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
        ImageDraw.Draw(base).ellipse([300, 200, 724, 800], fill=(230, 200, 180, 255))
        base.save(reference)
        edited = base.copy()
        ImageDraw.Draw(edited).ellipse([450, 620, 570, 700], fill=(120, 60, 60, 255))
        edited.save(asset)

        result = self.run_cli("--from-diff", reference, asset)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("changed area", result.stdout)
        self.assertIn("center", result.stdout)

    @unittest.skipIf(Image is None, "Pillow is required")
    def test_from_diff_on_identical_images(self):
        reference = self.repo / "ref.png"
        Image.new("RGBA", (1024, 1024), (0, 0, 0, 0)).save(reference)
        result = self.run_cli("--from-diff", reference, reference)
        self.assertEqual(result.returncode, 0)
        self.assertIn("identical", result.stdout)

    def test_from_diff_with_a_missing_file_is_a_usage_error(self):
        result = self.run_cli("--from-diff", self.repo / "a.png", self.repo / "b.png")
        self.assertEqual(result.returncode, 2)

    # --- CLI -------------------------------------------------------------

    def test_two_modes_at_once_is_a_usage_error(self):
        result = self.run_cli("--show", "--box", 442, 630, 582, 700)
        self.assertEqual(result.returncode, 2)

    def test_no_mode_is_a_usage_error(self):
        self.assertEqual(self.run_cli().returncode, 2)

    def test_edit_region_without_box_is_a_usage_error(self):
        result = self.run_cli("--show", "--edit-region", 400, 600, 630, 780)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
