#!/usr/bin/env python3
"""Tests for scripts/validation/validate_video.py (PHASE 9).

Each test breaks a plan the way a plan actually breaks and asserts the validator
names it. The point of the phase is that these are decidable before an encode, so
every one of them has to be caught here rather than in the output file.

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
SCRIPT = REPO / "scripts" / "validation" / "validate_video.py"
sys.path.insert(0, str(REPO / "scripts" / "validation"))
sys.path.insert(0, str(REPO / "scripts" / "lib"))
sys.path.insert(0, str(REPO / "tests"))

import validate_video                                 # noqa: E402
import videoplan                                      # noqa: E402
from video import fixtures                            # noqa: E402


class ValidateVideoTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        timeline = fixtures.timeline()
        cls.good = videoplan.build(fixtures.animation(timeline), timeline,
                                   move="slow-push", name="demo")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    # --- helpers ----------------------------------------------------------

    def plan(self, **changes):
        payload = json.loads(json.dumps(self.good))
        payload.update(changes)
        return payload

    def check(self, payload, reseal=True, strict=False):
        if reseal:
            payload["digest"] = videoplan.digest(payload)
        path = self.tmp / "plan.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return validate_video.validate(path, strict)

    def levels(self, report, name):
        return [level for level, entry, _ in report.rows if entry == name]

    # --- the good case ----------------------------------------------------

    def test_a_built_plan_validates(self):
        report, failed = self.check(self.plan(), reseal=False)
        self.assertFalse(failed, report.render())

    def test_unreadable_file_is_invalid(self):
        path = self.tmp / "broken.json"
        path.write_text("{not json")
        report, failed = validate_video.validate(path)
        self.assertTrue(failed)

    # --- canvas -----------------------------------------------------------

    def test_odd_canvas_dimension_fails(self):
        payload = self.plan()
        payload["canvas"]["height"] = 1081
        report, failed = self.check(payload)
        self.assertIn("FAIL", self.levels(report, "canvas/size"))
        self.assertTrue(failed)

    def test_fps_disagreeing_with_the_frame_plan_fails(self):
        payload = self.plan()
        payload["canvas"]["fps"] = 30
        self.assertIn("FAIL", self.levels(self.check(payload)[0], "canvas/fps"))

    def test_duration_disagreeing_with_the_frame_count_fails(self):
        payload = self.plan(duration=60.0)
        self.assertIn("FAIL", self.levels(self.check(payload)[0], "canvas/duration"))

    def test_a_plan_with_no_avatar_layer_fails(self):
        payload = self.plan()
        payload["layers"] = [layer for layer in payload["layers"]
                             if layer["kind"] != "avatar"]
        self.assertIn("FAIL", self.levels(self.check(payload)[0], "layers/avatar"))

    # --- camera -----------------------------------------------------------

    def test_camera_frame_count_mismatch_fails(self):
        payload = self.plan()
        payload["camera"]["frames"] = payload["camera"]["frames"][:10]
        self.assertIn("FAIL", self.levels(self.check(payload)[0], "camera/frames"))

    def test_an_unknown_easing_name_fails(self):
        payload = self.plan()
        payload["camera"]["keyframes"][0]["ease"] = "bounce.out"
        self.assertIn("FAIL", self.levels(self.check(payload)[0], "camera/easing"))

    def test_a_camera_that_upscales_is_warned_about(self):
        payload = self.plan()
        for frame in payload["camera"]["frames"]:
            frame["scale"] = 1.3
        self.assertIn("WARN", self.levels(self.check(payload)[0], "camera/resolution"))

    def test_losing_the_authoritative_marker_is_warned_about(self):
        payload = self.plan()
        del payload["camera"]["authoritative"]
        self.assertIn("WARN", self.levels(self.check(payload)[0], "camera/authority"))

    # --- subtitles --------------------------------------------------------

    def test_overlapping_cues_fail(self):
        payload = self.plan()
        payload["subtitles"]["cues"][1]["start"] = \
            payload["subtitles"]["cues"][0]["end"] - 0.5
        self.assertIn("FAIL", self.levels(self.check(payload)[0], "subtitle/overlap"))

    def test_a_cue_past_the_audio_fails(self):
        payload = self.plan()
        payload["subtitles"]["cues"][-1]["end"] = payload["duration"] + 2.0
        self.assertIn("FAIL", self.levels(self.check(payload)[0], "subtitle/bounds"))

    def test_a_backwards_cue_fails(self):
        payload = self.plan()
        cue = payload["subtitles"]["cues"][0]
        cue["start"], cue["end"] = cue["end"], cue["start"]
        self.assertIn("FAIL", self.levels(self.check(payload)[0], "subtitle/order"))

    def test_an_overlong_line_fails(self):
        payload = self.plan()
        payload["subtitles"]["cues"][0]["lines"] = ["ก" * 80]
        self.assertIn("FAIL", self.levels(self.check(payload)[0], "subtitle/layout"))

    def test_too_many_lines_fails(self):
        payload = self.plan()
        payload["subtitles"]["cues"][0]["lines"] = ["ก", "ข", "ค"]
        self.assertIn("FAIL", self.levels(self.check(payload)[0], "subtitle/layout"))

    def test_an_empty_cue_fails(self):
        payload = self.plan()
        payload["subtitles"]["cues"][0]["text"] = "  "
        self.assertIn("FAIL", self.levels(self.check(payload)[0], "subtitle/text"))

    def test_a_fast_cue_is_warned_about(self):
        payload = self.plan()
        payload["subtitles"]["cues"][0]["too_fast"] = True
        self.assertIn("WARN", self.levels(self.check(payload)[0],
                                          "subtitle/reading-speed"))

    def test_burn_in_without_ass_fails(self):
        payload = self.plan()
        payload["subtitles"]["burn_in"] = True
        payload["subtitles"]["format"] = "srt"
        self.assertIn("FAIL", self.levels(self.check(payload)[0], "subtitle/burn-in"))

    def test_a_plan_with_no_subtitles_is_skipped_not_failed(self):
        payload = self.plan()
        payload["subtitles"]["cues"] = []
        report, failed = self.check(payload)
        self.assertIn("SKIP", self.levels(report, "subtitle/cues"))
        self.assertFalse(failed)

    # --- render and source ------------------------------------------------

    def test_an_unimplemented_engine_fails(self):
        payload = self.plan()
        payload["render"]["engine"] = "hyperframes"
        self.assertIn("FAIL", self.levels(self.check(payload)[0], "render/engine"))

    def test_an_unknown_profile_fails(self):
        payload = self.plan()
        payload["render"]["profile"] = "imax"
        self.assertIn("FAIL", self.levels(self.check(payload)[0], "render/profile"))

    def test_an_unplayable_pixel_format_is_warned_about(self):
        payload = self.plan()
        payload["render"]["pixel_format"] = "yuv444p"
        self.assertIn("WARN", self.levels(self.check(payload)[0],
                                          "render/pixel-format"))

    def test_a_plan_with_no_frame_plan_digest_fails(self):
        payload = self.plan()
        payload["source_animation"]["digest"] = None
        self.assertIn("FAIL", self.levels(self.check(payload)[0], "source/animation"))

    def test_estimated_timing_is_warned_about(self):
        payload = self.plan()
        payload["source_timeline"]["timing_source"] = "estimated"
        self.assertIn("WARN", self.levels(self.check(payload)[0], "source/timing"))

    # --- digest -----------------------------------------------------------

    def test_an_edited_plan_fails_its_digest(self):
        payload = self.plan()
        payload["subtitles"]["cues"][0]["text"] = "ถูกแก้ไข"
        report, failed = self.check(payload, reseal=False)
        self.assertIn("FAIL", self.levels(report, "lock/digest"))
        self.assertTrue(failed)

    def test_a_missing_digest_fails(self):
        payload = self.plan()
        del payload["digest"]
        report, failed = validate_video.validate(
            self._write(payload), False)
        self.assertIn("FAIL", self.levels(report, "lock/digest"))

    def _write(self, payload):
        path = self.tmp / "nodigest.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    # --- strict and the CLI -----------------------------------------------

    def test_strict_turns_a_warning_into_a_failure(self):
        payload = self.plan()
        payload["source_timeline"]["timing_source"] = "estimated"
        self.assertFalse(self.check(payload)[1])
        self.assertTrue(self.check(payload, strict=True)[1])

    def test_cli_all_on_an_empty_directory_is_not_an_error(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--all"],
                                capture_output=True, text=True,
                                env=dict(os.environ, NARRA_REPO=str(self.tmp)))
        self.assertEqual(result.returncode, 0)

    def test_cli_needs_a_target(self):
        result = subprocess.run([sys.executable, str(SCRIPT)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)

    def test_cli_reports_a_valid_plan(self):
        path = videoplan.write(self.good, self.tmp / "videos" / "demo-video-v1.json")
        result = subprocess.run([sys.executable, str(SCRIPT), str(path)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("valid", result.stdout)


if __name__ == "__main__":
    unittest.main()
