#!/usr/bin/env python3
"""Tests for scripts/video/build_video.py (PHASE 9).

The behaviour worth pinning is the refusal: a plan built against a timeline that is
not the one the frame plan was animated from would carry the right mouth shapes and
the wrong words, and nothing downstream would notice. So the timeline is found by
digest, and a miss is an error rather than a nearest match.

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
SCRIPT = REPO / "scripts" / "video" / "build_video.py"
sys.path.insert(0, str(REPO / "tests"))

from video import fixtures                            # noqa: E402


class BuildVideoTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        for part in ("metadata/timelines", "metadata/animations", "metadata/videos",
                     "assets/video", "assets/audio"):
            (self.repo / part).mkdir(parents=True)
        self.addCleanup(self._tmp.cleanup)

        self.timeline = fixtures.timeline()
        self.animation = fixtures.animation(self.timeline)
        self.timeline_path = self.write("metadata/timelines/demo-timeline-v1.json",
                                        self.timeline)
        self.animation_path = self.write("metadata/animations/demo-animation-v1.json",
                                         self.animation)

    def write(self, relative, payload):
        path = self.repo / relative
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def build(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              capture_output=True, text=True,
                              env=dict(os.environ, NARRA_REPO=str(self.repo)))

    def plan(self, *args):
        result = self.build(str(self.animation_path), *args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        written = self.repo / "metadata" / "videos" / "demo-video-v1.json"
        return json.loads(written.read_text(encoding="utf-8"))

    # --- the happy path ---------------------------------------------------

    def test_writes_a_plan_and_a_sidecar(self):
        plan = self.plan()
        self.assertEqual(plan["phase"], "9")
        sidecar = self.repo / "assets" / "video" / "demo.srt"
        self.assertTrue(sidecar.exists())
        self.assertIn("-->", sidecar.read_text(encoding="utf-8"))

    def test_sidecar_holds_thai_text(self):
        self.plan()
        body = (self.repo / "assets" / "video" / "demo.srt").read_text(encoding="utf-8")
        self.assertIn("สวัสดี", body)

    def test_camera_move_reaches_the_plan(self):
        self.assertEqual(self.plan("--move", "slow-push")["camera"]["move"],
                         "slow-push")

    def test_canvas_override(self):
        plan = self.plan("--canvas", "1080x1080")
        self.assertEqual((plan["canvas"]["width"], plan["canvas"]["height"]),
                         (1080, 1080))

    def test_ass_sidecar_when_asked_for(self):
        self.plan("--subtitle-format", "ass")
        self.assertTrue((self.repo / "assets" / "video" / "demo.ass").exists())

    def test_no_subtitles_writes_no_sidecar(self):
        plan = self.plan("--no-subtitles")
        self.assertEqual(plan["subtitles"]["cue_count"], 0)
        self.assertEqual(list((self.repo / "assets" / "video").glob("*.srt")), [])

    # --- refusals ---------------------------------------------------------

    def test_a_timeline_that_does_not_match_is_refused(self):
        self.timeline_path.unlink()
        other = fixtures.timeline("ขอบคุณครับ", duration=2.0)
        self.write("metadata/timelines/other-timeline-v1.json", other)
        result = self.build(str(self.animation_path))
        self.assertEqual(result.returncode, 1)
        self.assertIn("no timeline", result.stderr)

    def test_no_timeline_is_fine_without_subtitles(self):
        self.timeline_path.unlink()
        result = self.build(str(self.animation_path), "--no-subtitles")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_an_explicit_timeline_is_used(self):
        self.timeline_path.unlink()
        elsewhere = self.write("metadata/other.json", self.timeline)
        result = self.build(str(self.animation_path), "--timeline", str(elsewhere))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_missing_animation_is_an_error(self):
        result = self.build(str(self.repo / "nope.json"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("cannot read", result.stderr)

    def test_an_unknown_move_is_an_error(self):
        result = self.build(str(self.animation_path), "--move", "crash-zoom")
        self.assertEqual(result.returncode, 1)
        self.assertIn("camera move", result.stderr)

    def test_an_unknown_profile_is_an_error(self):
        result = self.build(str(self.animation_path), "--profile", "imax")
        self.assertEqual(result.returncode, 1)

    # --- report mode ------------------------------------------------------

    def test_report_writes_nothing(self):
        result = self.build(str(self.animation_path), "--report")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list((self.repo / "metadata" / "videos").glob("*.json")), [])
        self.assertEqual(list((self.repo / "assets" / "video").glob("*")), [])

    def test_report_names_the_camera_and_the_cues(self):
        result = self.build(str(self.animation_path), "--report", "--move", "slow-push")
        self.assertIn("slow-push", result.stdout)
        self.assertIn("cue(s)", result.stdout)

    def test_json_report_is_the_plan(self):
        result = self.build(str(self.animation_path), "--report", "--json")
        self.assertEqual(json.loads(result.stdout)["phase"], "9")

    def test_estimated_timing_is_surfaced(self):
        estimated = dict(self.timeline, timing_source="estimated")
        self.animation["source_timeline"]["timing_source"] = "estimated"
        self.write("metadata/animations/demo-animation-v1.json", self.animation)
        self.write("metadata/timelines/demo-timeline-v1.json", estimated)
        result = self.build(str(self.animation_path), "--report")
        self.assertIn("estimated", result.stdout)


if __name__ == "__main__":
    unittest.main()
