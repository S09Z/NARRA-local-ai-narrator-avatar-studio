#!/usr/bin/env python3
"""Tests for scripts/lib/camera.py (PHASE 9).

Two things are load-bearing. The easing curves must match GSAP's, because the
sampled values are the contract between an ffmpeg render and a browser one and a
curve that is merely close reads as judder. And the limits must catch a push-in that
has become an upscale, which is the one camera mistake this pipeline can make that
no amount of prompt or asset work can undo.

Run:
    python3 -m unittest discover -s tests -p 'test_*.py' -v
"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "lib"))

import camera                                         # noqa: E402


def levels(findings, name):
    return [level for level, entry, _ in findings if entry == name]


class EasingTest(unittest.TestCase):

    def test_none_is_linear(self):
        curve = camera.easing("none")
        for value in (0.0, 0.25, 0.5, 0.75, 1.0):
            self.assertAlmostEqual(curve(value), value)

    def test_every_supported_easing_spans_zero_to_one(self):
        for name in camera.supported_easings():
            with self.subTest(easing=name):
                curve = camera.easing(name)
                self.assertAlmostEqual(curve(0.0), 0.0, places=9)
                self.assertAlmostEqual(curve(1.0), 1.0, places=9)

    def test_every_supported_easing_is_monotonic(self):
        for name in camera.supported_easings():
            with self.subTest(easing=name):
                curve = camera.easing(name)
                values = [curve(index / 40) for index in range(41)]
                for before, after in zip(values, values[1:]):
                    self.assertLessEqual(before, after + 1e-12)

    def test_gsap_power_exponents(self):
        """power1/2/3 are quadratic, cubic, quartic - not 1, 2, 3."""
        self.assertAlmostEqual(camera.easing("power1.in")(0.5), 0.25)
        self.assertAlmostEqual(camera.easing("power2.in")(0.5), 0.125)
        self.assertAlmostEqual(camera.easing("power3.in")(0.5), 0.0625)

    def test_in_out_is_symmetric_about_the_midpoint(self):
        for name in ("power1.inOut", "power2.inOut", "sine.inOut"):
            with self.subTest(easing=name):
                curve = camera.easing(name)
                self.assertAlmostEqual(curve(0.5), 0.5, places=9)
                for value in (0.1, 0.3):
                    self.assertAlmostEqual(curve(value) + curve(1 - value), 1.0,
                                           places=9)

    def test_unknown_easing_is_refused(self):
        for name in ("bounce.out", "power9.in", "power1.sideways"):
            with self.subTest(easing=name):
                with self.assertRaises(camera.CameraError):
                    camera.easing(name)


class MoveTest(unittest.TestCase):

    def test_named_moves_resolve(self):
        model = camera.load_model()
        for name in (key for key in model["moves"] if not key.startswith("$")):
            with self.subTest(move=name):
                self.assertTrue(camera.resolve_move(name))

    def test_unknown_move_is_refused(self):
        with self.assertRaises(camera.CameraError):
            camera.resolve_move("crash-zoom")

    def test_explicit_keyframes_are_accepted(self):
        frames = camera.resolve_move({"keyframes": [{"t": 0, "scale": 1.0},
                                                    {"t": 1, "scale": 1.1}]})
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0]["ease"],
                         camera.load_model()["easing"]["default"])

    def test_keyframes_outside_zero_to_one_are_refused(self):
        with self.assertRaises(camera.CameraError):
            camera.resolve_move([{"t": 1.5, "scale": 1.0}])

    def test_duplicate_keyframe_times_are_refused(self):
        with self.assertRaises(camera.CameraError):
            camera.resolve_move([{"t": 0.5, "scale": 1.0}, {"t": 0.5, "scale": 1.2}])

    def test_empty_keyframes_are_refused(self):
        with self.assertRaises(camera.CameraError):
            camera.resolve_move([])


class SampleTest(unittest.TestCase):

    def test_one_entry_per_frame(self):
        track = camera.track("slow-push", 60, 25)
        self.assertEqual(len(track["frames"]), 60)
        self.assertEqual([frame["frame"] for frame in track["frames"]],
                         list(range(60)))

    def test_endpoints_match_the_keyframes(self):
        track = camera.track("slow-push", 60, 25)
        self.assertAlmostEqual(track["frames"][0]["scale"], 1.0)
        self.assertAlmostEqual(track["frames"][-1]["scale"], 1.08)

    def test_a_single_frame_clip_samples_the_first_keyframe(self):
        track = camera.track("slow-push", 1, 25)
        self.assertEqual(len(track["frames"]), 1)
        self.assertAlmostEqual(track["frames"][0]["scale"], 1.0)

    def test_zero_frames_samples_nothing(self):
        self.assertEqual(camera.sample(camera.resolve_move("static"), 0, 25), [])

    def test_static_never_moves(self):
        track = camera.track("static", 30, 25)
        self.assertEqual({frame["scale"] for frame in track["frames"]}, {1.0})
        self.assertEqual({frame["x"] for frame in track["frames"]}, {0.0})

    def test_frame_times_follow_the_frame_rate(self):
        track = camera.track("static", 30, 25)
        for frame in track["frames"]:
            self.assertAlmostEqual(frame["time"], frame["frame"] / 25, places=4)

    def test_sampled_frames_are_marked_authoritative(self):
        """ADR-032: two renderers agree because they read the same samples."""
        track = camera.track("slow-push", 10, 25)
        self.assertEqual(track["authoritative"], "frames")
        self.assertEqual(track["easing_vocabulary"], "gsap")


class LimitTest(unittest.TestCase):

    def test_a_slow_push_on_a_medium_asset_passes(self):
        findings = camera.check_limits(camera.track("slow-push", 118, 25),
                                       "medium", 4.73)
        self.assertNotIn("FAIL", [level for level, _, _ in findings])

    def test_scale_beyond_the_model_limit_fails(self):
        track = camera.track([{"t": 0, "scale": 1.0}, {"t": 1, "scale": 2.0}], 60, 25)
        self.assertIn("FAIL", levels(camera.check_limits(track, "medium", 4.0),
                                     "camera/scale"))

    def test_upscaling_is_warned_about(self):
        """The one camera error that cannot be undone downstream."""
        track = camera.track([{"t": 0, "scale": 1.0}, {"t": 1, "scale": 1.3}], 60, 25)
        self.assertIn("WARN", levels(camera.check_limits(track, "three-quarter", 20.0),
                                     "camera/resolution"))

    def test_pushing_a_close_up_past_its_framing_is_warned_about(self):
        track = camera.track("slow-push", 60, 25)
        self.assertIn("WARN", levels(camera.check_limits(track, "close-up", 10.0),
                                     "camera/class"))

    def test_a_fast_move_is_warned_about(self):
        track = camera.track([{"t": 0, "scale": 1.0}, {"t": 1, "scale": 1.3}], 25, 25)
        self.assertIn("WARN", levels(camera.check_limits(track, "medium", 1.0),
                                     "camera/speed"))

    def test_a_large_pan_fails(self):
        track = camera.track([{"t": 0, "scale": 1.0, "x": 0.0},
                              {"t": 1, "scale": 1.0, "x": 0.4}], 60, 25)
        self.assertIn("FAIL", levels(camera.check_limits(track, "medium", 30.0),
                                     "camera/pan"))

    def test_an_unknown_camera_class_is_warned_about(self):
        track = camera.track("static", 10, 25)
        self.assertIn("WARN", levels(camera.check_limits(track, "extreme-close-up", 1.0),
                                     "camera/class"))

    def test_an_empty_track_fails(self):
        self.assertIn("FAIL", levels(camera.check_limits({"frames": []}), "camera/frames"))

    def test_sampling_ratio_is_output_pixels_per_source_pixel(self):
        model = camera.load_model()
        expected = (model["canvas"]["height"] * model["avatar"]["height_fraction"]
                    / model["avatar"]["source_resolution"])
        self.assertAlmostEqual(camera.sampling_ratio(1.0), expected)
        self.assertAlmostEqual(camera.sampling_ratio(2.0), expected * 2)

    def test_class_scale_limit_is_the_inverse_of_the_head_ratio(self):
        self.assertAlmostEqual(camera.class_scale_limit("close-up"), 1.0)
        self.assertAlmostEqual(camera.class_scale_limit("medium"), 1 / 0.71, places=6)
        self.assertIsNone(camera.class_scale_limit("nope"))


class ModelTest(unittest.TestCase):

    def test_unreadable_model_is_refused(self):
        with self.assertRaises(camera.CameraError):
            camera.load_model(REPO / "docs" / "video" / "missing.json")

    def test_every_move_in_the_model_stays_inside_the_limits(self):
        """A shipped preset that violates the shipped limits is a contradiction."""
        model = camera.load_model()
        for name in (key for key in model["moves"] if not key.startswith("$")):
            with self.subTest(move=name):
                track = camera.track(name, 250, 25)
                self.assertNotIn("FAIL", [level for level, _, _ in
                                          camera.check_limits(track, "medium", 10.0)])


if __name__ == "__main__":
    unittest.main()
