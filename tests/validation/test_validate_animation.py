#!/usr/bin/env python3
"""Tests for scripts/validation/validate_animation.py (PHASE 8).

Each test breaks a known-good frame plan in exactly one way and asserts the tool
notices. A validator that only ever passes is decoration.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "validation" / "validate_animation.py"

sys.path.insert(0, str(REPO / "scripts" / "lib"))
import animation as animation_lib     # noqa: E402
import thai_g2p                       # noqa: E402
import timeline as timeline_lib       # noqa: E402

TALKING = {"pose": "neutral", "camera_class": "medium", "expression": "neutral",
           "mouth": "viseme-track", "idle_viseme": "REST"}


def good_plan(fps=25, duration=1.6):
    payload = timeline_lib.build(thai_g2p.phonemize("สวัสดีครับ"),
                                 audio_duration=duration, generated="X")
    return animation_lib.build(payload, TALKING, "talking", fps, generated="X")


class ValidateAnimationTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.work = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def run_on(self, plan, reseal=True, *extra):
        if reseal:
            plan["digest"] = animation_lib.digest(plan)
        path = self.work / "a.json"
        path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        return subprocess.run([sys.executable, str(SCRIPT), str(path), *extra],
                              capture_output=True, text=True)

    # --- the good case ---------------------------------------------------------------

    def test_a_generated_plan_is_valid(self):
        result = self.run_on(good_plan(), reseal=False)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("valid", result.stdout)

    # --- one break at a time ---------------------------------------------------------

    def test_weights_that_do_not_sum_to_one_fail(self):
        plan = good_plan()
        plan["tracks"]["mouth"][4]["layers"] = [{"viseme": "A", "weight": 0.4}]
        result = self.run_on(plan)
        self.assertEqual(result.returncode, 1)
        self.assertIn("weights/normalised", result.stdout)

    def test_too_many_layers_fail(self):
        plan = good_plan()
        plan["tracks"]["mouth"][4]["layers"] = [
            {"viseme": "A", "weight": 0.34}, {"viseme": "I", "weight": 0.33},
            {"viseme": "U", "weight": 0.33}]
        result = self.run_on(plan)
        self.assertEqual(result.returncode, 1)
        self.assertIn("weights/layer-count", result.stdout)

    def test_a_shape_blended_with_itself_fails(self):
        plan = good_plan()
        plan["tracks"]["mouth"][4]["layers"] = [
            {"viseme": "A", "weight": 0.5}, {"viseme": "A", "weight": 0.5}]
        result = self.run_on(plan)
        self.assertEqual(result.returncode, 1)
        self.assertIn("weights/distinct", result.stdout)

    def test_a_non_canonical_viseme_fails(self):
        plan = good_plan()
        plan["tracks"]["mouth"][4]["layers"] = [{"viseme": "ZZ", "weight": 1.0}]
        result = self.run_on(plan)
        self.assertEqual(result.returncode, 1)
        self.assertIn("viseme/canonical", result.stdout)

    def test_frames_out_of_order_fail(self):
        plan = good_plan()
        plan["tracks"]["mouth"][3]["frame"] = 99
        result = self.run_on(plan)
        self.assertEqual(result.returncode, 1)
        self.assertIn("frames/sequential", result.stdout)

    def test_a_frame_time_off_the_grid_fails(self):
        plan = good_plan()
        plan["tracks"]["mouth"][3]["time"] = 5.0
        result = self.run_on(plan)
        self.assertEqual(result.returncode, 1)
        self.assertIn("frames/time", result.stdout)

    def test_a_frame_count_that_disagrees_fails(self):
        plan = good_plan()
        plan["frame_count"] = 3
        result = self.run_on(plan)
        self.assertEqual(result.returncode, 1)
        self.assertIn("frames/count", result.stdout)

    def test_a_one_frame_flicker_fails(self):
        """mapping.md section 6 - the failure this rule exists to prevent."""
        plan = good_plan()
        frames = plan["tracks"]["mouth"]
        for index, viseme in ((10, "A"), (11, "SH"), (12, "A")):
            frames[index]["layers"] = [{"viseme": viseme, "weight": 1.0}]
        result = self.run_on(plan)
        self.assertEqual(result.returncode, 1)
        self.assertIn("frames/min-hold", result.stdout)

    def test_a_closure_that_never_closes_fails(self):
        plan = good_plan()
        for frame in plan["tracks"]["mouth"]:
            for layer in frame["layers"]:
                if layer["viseme"] == "MBP" and layer["weight"] >= 0.999:
                    frame["layers"] = [{"viseme": "MBP", "weight": 0.8},
                                       {"viseme": "A", "weight": 0.2}]
        result = self.run_on(plan)
        self.assertEqual(result.returncode, 1)
        self.assertIn("closure/full-weight", result.stdout)

    def test_an_unresolved_closure_is_reported(self):
        plan = good_plan()
        plan["mouth_meta"]["closures"] = [
            {"viseme": "MBP", "resolved": False, "reason": "between frames"}]
        result = self.run_on(plan)
        self.assertEqual(result.returncode, 1)
        self.assertIn("closure/complete", result.stdout)

    def test_a_starved_closure_is_reported(self):
        plan = good_plan()
        plan["mouth_meta"]["extended"] = [
            {"viseme": "MBP", "wanted": 0.08, "given": 0.0, "reason": "no donor"}]
        result = self.run_on(plan)
        self.assertEqual(result.returncode, 1)
        self.assertIn("closure/visible", result.stdout)

    def test_an_open_mouth_expression_under_a_track_fails(self):
        """ADR-012 - this is the check that stops two mouths being rendered."""
        plan = good_plan()
        for segment in plan["tracks"]["expression"]:
            segment["expression"] = "surprised"
        result = self.run_on(plan)
        self.assertEqual(result.returncode, 1)
        self.assertIn("expression/open-mouth", result.stdout)

    def test_a_gap_in_the_expression_track_fails(self):
        plan = good_plan()
        plan["tracks"]["expression"] = [
            {"start": 0.0, "end": 0.5, "expression": "neutral"},
            {"start": 0.9, "end": plan["duration"], "expression": "happy"}]
        result = self.run_on(plan)
        self.assertEqual(result.returncode, 1)
        self.assertIn("expression/contiguous", result.stdout)

    def test_an_expression_track_that_ends_early_fails(self):
        plan = good_plan()
        plan["tracks"]["expression"] = [
            {"start": 0.0, "end": 0.5, "expression": "neutral"}]
        result = self.run_on(plan)
        self.assertEqual(result.returncode, 1)
        self.assertIn("expression/duration", result.stdout)

    def test_a_blink_outside_the_duration_fails(self):
        plan = good_plan()
        plan["tracks"]["blink"] = [{"start": 99.0, "end": 99.2}]
        result = self.run_on(plan)
        self.assertEqual(result.returncode, 1)
        self.assertIn("secondary/blink", result.stdout)

    def test_a_breath_track_of_the_wrong_length_fails(self):
        plan = good_plan()
        plan["tracks"]["breath"]["values"] = [0.0, 0.1]
        result = self.run_on(plan)
        self.assertEqual(result.returncode, 1)
        self.assertIn("secondary/breath", result.stdout)

    def test_a_hand_edited_file_fails_the_digest(self):
        plan = good_plan()
        plan["fps"] = 30
        result = self.run_on(plan, reseal=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("lock/digest", result.stdout)

    def test_a_zero_fps_fails(self):
        plan = good_plan()
        plan["fps"] = 0
        result = self.run_on(plan)
        self.assertEqual(result.returncode, 1)
        self.assertIn("fps", result.stdout)

    def test_an_estimated_source_warns(self):
        payload = timeline_lib.build(thai_g2p.phonemize("สวัสดีครับ"), generated="X")
        plan = animation_lib.build(payload, TALKING, "talking", 25, generated="X")
        result = self.run_on(plan, reseal=False)
        self.assertIn("source/timing", result.stdout)
        self.assertEqual(result.returncode, 0)

    def test_strict_turns_that_warning_into_a_failure(self):
        payload = timeline_lib.build(thai_g2p.phonemize("สวัสดีครับ"), generated="X")
        plan = animation_lib.build(payload, TALKING, "talking", 25, generated="X")
        result = self.run_on(plan, False, "--strict")
        self.assertEqual(result.returncode, 1)

    def test_a_static_state_skips_the_open_mouth_check(self):
        payload = timeline_lib.build(thai_g2p.phonemize("สวัสดีครับ"),
                                     audio_duration=1.6, generated="X")
        reaction = {"pose": "surprised", "camera_class": "medium",
                    "expression": "surprised", "mouth": "static", "idle_viseme": None}
        plan = animation_lib.build(payload, reaction, "reaction", 25, generated="X")
        result = self.run_on(plan, reseal=False)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("SKIP", result.stdout)

    def test_an_unreadable_file_fails(self):
        path = self.work / "broken.json"
        path.write_text("{nope", encoding="utf-8")
        result = subprocess.run([sys.executable, str(SCRIPT), str(path)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
