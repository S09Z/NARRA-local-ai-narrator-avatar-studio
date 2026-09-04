#!/usr/bin/env python3
"""Tests for scripts/lib/videoplan.py (PHASE 9).

The plan is the contract between everything that produces a video and everything
that renders one, so the things pinned here are the ones a renderer relies on: that
a plan cannot be built against a sentence it has no timeline for, that its digest
notices an edit, and that the canvas it declares is one an encoder will accept.

Run:
    python3 -m unittest discover -s tests -p 'test_*.py' -v
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "lib"))
sys.path.insert(0, str(REPO / "tests"))

import videoplan                                      # noqa: E402
from video import fixtures                            # noqa: E402


class BuildTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.timeline = fixtures.timeline()
        cls.animation = fixtures.animation(cls.timeline)

    def plan(self, **kwargs):
        return videoplan.build(self.animation, self.timeline, name="t", **kwargs)

    def test_plan_carries_what_a_renderer_needs(self):
        plan = self.plan()
        for field in ("schema_version", "canvas", "duration", "frame_count", "camera",
                      "subtitles", "layers", "render", "audio", "digest"):
            self.assertIn(field, plan)
        self.assertEqual(plan["phase"], "9")

    def test_canvas_inherits_the_frame_rate_from_the_animation(self):
        """A video at a different fps than its lip-sync drifts against its own audio."""
        plan = self.plan()
        self.assertEqual(plan["canvas"]["fps"], self.animation["fps"])
        self.assertEqual(plan["frame_count"], self.animation["frame_count"])

    def test_camera_track_matches_the_frame_count(self):
        plan = self.plan(move="slow-push")
        self.assertEqual(len(plan["camera"]["frames"]), plan["frame_count"])

    def test_odd_canvas_dimensions_are_rounded_down(self):
        plan = self.plan(canvas={"width": 1921, "height": 1081})
        self.assertEqual((plan["canvas"]["width"], plan["canvas"]["height"]),
                         (1920, 1080))

    def test_an_unrenderable_canvas_is_refused(self):
        with self.assertRaises(videoplan.VideoPlanError):
            self.plan(canvas={"width": 1, "height": 1})

    def test_layers_are_ordered_back_to_front(self):
        plan = videoplan.build(self.animation, self.timeline, name="t",
                               broll=[{"path": "b.mp4", "start": 0.0, "end": 1.0}])
        order = [layer["z"] for layer in plan["layers"]]
        self.assertEqual(order, sorted(order))
        self.assertEqual([layer["kind"] for layer in plan["layers"]][0], "broll")

    def test_subtitles_without_a_timeline_are_refused(self):
        """The cue text lives in the timeline; the frame plan carries no words."""
        with self.assertRaises(videoplan.VideoPlanError) as caught:
            videoplan.build(self.animation, None, subtitles=True)
        self.assertIn("timeline", str(caught.exception))

    def test_no_subtitles_needs_no_timeline(self):
        plan = videoplan.build(self.animation, None, subtitles=False, name="t")
        self.assertEqual(plan["subtitles"]["cue_count"], 0)
        self.assertNotIn("subtitle", [layer["kind"] for layer in plan["layers"]])

    def test_an_animation_without_fps_is_refused(self):
        broken = dict(self.animation, fps=None)
        with self.assertRaises(videoplan.VideoPlanError):
            videoplan.build(broken, self.timeline)

    def test_unknown_profile_is_refused(self):
        with self.assertRaises(videoplan.VideoPlanError):
            self.plan(profile="imax")

    def test_profile_settings_reach_the_plan(self):
        plan = self.plan(profile="review-720p")
        self.assertEqual(plan["render"]["profile"], "review-720p")
        self.assertEqual(plan["render"]["scale_height"], 720)

    def test_source_digests_are_recorded(self):
        plan = self.plan()
        self.assertEqual(plan["source_animation"]["digest"], self.animation["digest"])
        self.assertEqual(plan["source_timeline"]["digest"],
                         self.animation["source_timeline"]["digest"])


class DigestTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.timeline = fixtures.timeline()
        cls.animation = fixtures.animation(cls.timeline)

    def plan(self, **kwargs):
        return videoplan.build(self.animation, self.timeline, name="t", **kwargs)

    def test_digest_is_stable_across_rebuilds(self):
        first = self.plan(generated="2026-01-01T00:00:00Z")
        second = self.plan(generated="2030-06-06T06:06:06Z")
        self.assertEqual(first["digest"], second["digest"])

    def test_digest_changes_with_the_camera(self):
        self.assertNotEqual(self.plan(move="static")["digest"],
                            self.plan(move="slow-push")["digest"])

    def test_digest_changes_with_the_canvas(self):
        self.assertNotEqual(self.plan()["digest"],
                            self.plan(canvas={"width": 1080, "height": 1080})["digest"])

    def test_digest_notices_an_edited_cue(self):
        plan = self.plan()
        plan["subtitles"]["cues"][0]["text"] = "ไม่ใช่"
        self.assertNotEqual(videoplan.digest(plan), plan["digest"])


class IOTest(unittest.TestCase):

    def test_write_then_load_round_trips(self):
        timeline = fixtures.timeline()
        plan = videoplan.build(fixtures.animation(timeline), timeline, name="t")
        with tempfile.TemporaryDirectory() as tmp:
            path = videoplan.write(plan, Path(tmp) / "nested" / "plan.json")
            self.assertEqual(videoplan.load(path), plan)

    def test_thai_is_written_unescaped(self):
        timeline = fixtures.timeline()
        plan = videoplan.build(fixtures.animation(timeline), timeline, name="t")
        with tempfile.TemporaryDirectory() as tmp:
            path = videoplan.write(plan, Path(tmp) / "plan.json")
            self.assertIn("สวัสดี", path.read_text(encoding="utf-8"))

    def test_unreadable_plan_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "broken.json"
            broken.write_text("{not json")
            with self.assertRaises(videoplan.VideoPlanError):
                videoplan.load(broken)


class ProfileTest(unittest.TestCase):

    def test_every_shipped_profile_targets_a_playable_pixel_format(self):
        profiles = videoplan.load_profiles()["profiles"]
        for name, profile in profiles.items():
            with self.subTest(profile=name):
                self.assertEqual(profile["pixel_format"], "yuv420p")

    def test_the_default_engine_is_implemented(self):
        profiles = videoplan.load_profiles()
        default = profiles["engines"]["default"]
        self.assertEqual(profiles["engines"]["available"][default]["status"],
                         "implemented")

    def test_hyperframes_is_declared_and_honest_about_being_unimplemented(self):
        """PLAN section 9 names it; ADR-032 records why it is not wired up."""
        entry = videoplan.load_profiles()["engines"]["available"]["hyperframes"]
        self.assertNotEqual(entry["status"], "implemented")
        self.assertIn("blocked_on", entry)


if __name__ == "__main__":
    unittest.main()
