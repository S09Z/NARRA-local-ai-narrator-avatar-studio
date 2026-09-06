#!/usr/bin/env python3
"""Tests for scripts/lib/animation.py (PHASE 8).

The rules under test are the ones that make Thai lip-sync look Thai. mapping.md names
the failure modes directly - a released final stop, a bilabial that does not close, a
shape held for one frame - so each one gets a test that would catch it coming back.
"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "lib"))
import animation as animation_lib     # noqa: E402
import canon                          # noqa: E402
import thai_g2p                       # noqa: E402
import timeline as timeline_lib       # noqa: E402

FPS = 25
TALKING = {"pose": "neutral", "camera_class": "medium", "expression": "neutral",
           "mouth": "viseme-track", "idle_viseme": "REST"}
REACTION = {"pose": "surprised", "camera_class": "medium", "expression": "surprised",
            "mouth": "static", "idle_viseme": None}


def timeline_for(text, duration):
    return timeline_lib.build(thai_g2p.phonemize(text), audio_duration=duration,
                              generated="2026-08-27T00:00:00Z")


def plan_for(text="สวัสดีครับ", duration=1.5, state=None, fps=FPS, expressions=None):
    return animation_lib.build(timeline_for(text, duration), state or TALKING,
                               "talking", fps, expressions, generated="X")


def events(*specs):
    """(viseme, start, end, phoneme) tuples into timeline-shaped events."""
    return [{"viseme": viseme, "start": start, "end": end, "phoneme": phoneme,
             "role": role, "syllable": 0}
            for viseme, start, end, phoneme, role in specs]


class FramePlanTest(unittest.TestCase):

    def setUp(self):
        self.plan = plan_for()

    def test_frames_are_sequential_and_on_the_grid(self):
        for index, frame in enumerate(self.plan["tracks"]["mouth"]):
            self.assertEqual(frame["frame"], index)
            self.assertAlmostEqual(frame["time"], index / FPS, delta=0.001)

    def test_every_frame_sums_to_one(self):
        for frame in self.plan["tracks"]["mouth"]:
            total = sum(layer["weight"] for layer in frame["layers"])
            self.assertAlmostEqual(total, 1.0, delta=0.005)

    def test_no_frame_carries_the_same_shape_twice(self):
        for frame in self.plan["tracks"]["mouth"]:
            names = [layer["viseme"] for layer in frame["layers"]]
            self.assertEqual(len(names), len(set(names)))

    def test_at_most_two_layers(self):
        for frame in self.plan["tracks"]["mouth"]:
            self.assertLessEqual(len(frame["layers"]), 2)

    def test_all_visemes_are_canonical(self):
        for frame in self.plan["tracks"]["mouth"]:
            for layer in frame["layers"]:
                self.assertIn(layer["viseme"], canon.VISEMES)

    def test_frame_count_follows_fps(self):
        for fps in (24, 25, 30, 60):
            plan = plan_for(fps=fps)
            self.assertEqual(plan["fps"], fps)
            self.assertAlmostEqual(plan["frame_count"] / fps, plan["duration"],
                                   delta=0.05)


class CoarticulationTest(unittest.TestCase):
    """PLAN 8.2, with the rules from mapping.md sections 3 and 6."""

    def setUp(self):
        self.model = animation_lib.load_coarticulation()

    def test_transitions_blend_rather_than_cut(self):
        plan = plan_for()
        blended = [frame for frame in plan["tracks"]["mouth"]
                   if len(frame["layers"]) == 2]
        self.assertTrue(blended, "nothing blended - the mouth is cutting, not moving")

    def test_an_unreleased_final_holds_past_its_own_end(self):
        """mapping.md section 3 - the closure does not pop open. The transition is
        pushed after the boundary, so the shape is still full weight at its end."""
        track = events(("A", 0.0, 0.4, "aː", "vowel"),
                       ("MBP", 0.4, 0.7, "p̚", "final"),
                       ("KG", 0.7, 1.1, "kʰ", "initial"))
        windows = animation_lib.boundary_windows(track, self.model)
        before, after = windows[1]
        self.assertEqual(before, 0.0, "the closure is being crossfaded away early")
        self.assertGreater(after, 0.0)

    def test_a_released_initial_still_crossfades_normally(self):
        """A final merged into a following initial ('t̚+d') does open into the vowel;
        suppressing that release would be wrong in the other direction."""
        track = events(("A", 0.0, 0.4, "aː", "vowel"),
                       ("N", 0.4, 0.7, "t̚+d", "final"),
                       ("I", 0.7, 1.1, "iː", "vowel"))
        before, after = animation_lib.boundary_windows(track, self.model)[1]
        self.assertGreater(before, 0.0)

    def test_a_rounded_vowel_reaches_back_further(self):
        """mapping.md section 6 - /k/ before /u/ is already rounding."""
        rounded = events(("KG", 0.0, 0.4, "kʰ", "initial"),
                         ("U", 0.4, 0.9, "uː", "vowel"))
        plain = events(("KG", 0.0, 0.4, "kʰ", "initial"),
                       ("A", 0.4, 0.9, "aː", "vowel"))
        rounded_before = animation_lib.boundary_windows(rounded, self.model)[0][0]
        plain_before = animation_lib.boundary_windows(plain, self.model)[0][0]
        self.assertGreater(rounded_before, plain_before)

    def test_a_blend_never_outlasts_its_shorter_neighbour(self):
        track = events(("A", 0.0, 0.5, "aː", "vowel"),
                       ("I", 0.5, 0.53, "i", "vowel"),
                       ("A", 0.53, 1.0, "aː", "vowel"))
        for index, (before, after) in enumerate(
                animation_lib.boundary_windows(track, self.model)):
            shorter = min(track[index]["end"] - track[index]["start"],
                          track[index + 1]["end"] - track[index + 1]["start"])
            self.assertLessEqual(before + after, shorter + 1e-9)

    def test_smoothstep_is_eased_not_linear(self):
        self.assertAlmostEqual(animation_lib._smoothstep(0.5), 0.5)
        self.assertLess(animation_lib._smoothstep(0.25), 0.25)
        self.assertGreater(animation_lib._smoothstep(0.75), 0.75)


class FlickerTest(unittest.TestCase):
    """mapping.md section 6, in frames rather than seconds."""

    def setUp(self):
        self.model = animation_lib.load_coarticulation()

    def test_a_shape_too_brief_to_read_is_absorbed(self):
        track = events(("A", 0.0, 0.4, "aː", "vowel"),
                       ("I", 0.4, 0.41, "i", "vowel"),
                       ("E", 0.41, 0.9, "eː", "vowel"))
        kept, absorbed, _ = animation_lib.absorb_short_events(track, FPS, self.model)
        self.assertEqual([entry["viseme"] for entry in absorbed], ["I"])
        self.assertNotIn("I", [entry["viseme"] for entry in kept])

    def test_absorption_never_leaves_a_gap(self):
        track = events(("A", 0.0, 0.4, "aː", "vowel"),
                       ("I", 0.4, 0.41, "i", "vowel"),
                       ("E", 0.41, 0.9, "eː", "vowel"))
        kept, _, _ = animation_lib.absorb_short_events(track, FPS, self.model)
        self.assertAlmostEqual(kept[0]["start"], 0.0)
        self.assertAlmostEqual(kept[-1]["end"], 0.9)
        for before, after in zip(kept, kept[1:]):
            self.assertAlmostEqual(before["end"], after["start"], delta=1e-9)

    def test_absorption_merges_neighbours_that_become_identical(self):
        """Removing the shape between two identical ones leaves one hold, not two."""
        track = events(("A", 0.0, 0.4, "aː", "vowel"),
                       ("I", 0.4, 0.41, "i", "vowel"),
                       ("A", 0.41, 0.9, "aː", "vowel"))
        kept, _, _ = animation_lib.absorb_short_events(track, FPS, self.model)
        self.assertEqual([entry["viseme"] for entry in kept], ["A"])

    def test_every_hold_survives_at_least_the_minimum(self):
        minimum = self.model["min_frames_on_screen"] / FPS
        track = events(("A", 0.0, 0.4, "aː", "vowel"),
                       ("I", 0.4, 0.41, "i", "vowel"),
                       ("E", 0.41, 0.9, "eː", "vowel"))
        kept, _, _ = animation_lib.absorb_short_events(track, FPS, self.model)
        for entry in kept:
            self.assertGreaterEqual(entry["end"] - entry["start"], minimum - 1e-9)


class ClosureTest(unittest.TestCase):
    """CLAUDE.md - MBP must be visually distinct from REST, so it must actually close."""

    def setUp(self):
        self.model = animation_lib.load_coarticulation()

    def test_a_brief_closure_is_extended_not_absorbed(self):
        """Deleting a /p/ does not smooth the animation, it changes the word."""
        track = events(("A", 0.0, 0.5, "aː", "vowel"),
                       ("MBP", 0.5, 0.51, "p̚", "final"),
                       ("A", 0.51, 1.1, "aː", "vowel"))
        kept, absorbed, extended = animation_lib.absorb_short_events(
            track, FPS, self.model)
        self.assertNotIn("MBP", [entry["viseme"] for entry in absorbed])
        self.assertIn("MBP", [entry["viseme"] for entry in kept])
        self.assertTrue(extended)

    def test_an_extended_closure_reaches_the_minimum(self):
        minimum = self.model["min_frames_on_screen"] / FPS
        track = events(("A", 0.0, 0.5, "aː", "vowel"),
                       ("MBP", 0.5, 0.51, "p̚", "final"),
                       ("A", 0.51, 1.1, "aː", "vowel"))
        kept, _, _ = animation_lib.absorb_short_events(track, FPS, self.model)
        closure = [entry for entry in kept if entry["viseme"] == "MBP"][0]
        self.assertGreaterEqual(closure["end"] - closure["start"], minimum - 1e-9)

    def test_every_closure_reaches_full_weight_on_a_frame(self):
        for text, duration in [("สวัสดีครับ", 1.5), ("ขอบคุณมาก", 1.2),
                               ("ผมชื่อนารา", 1.6)]:
            plan = plan_for(text, duration)
            frames = plan["tracks"]["mouth"]
            present = {layer["viseme"] for frame in frames for layer in frame["layers"]}
            if "MBP" not in present:
                continue
            with self.subTest(text=text):
                self.assertTrue(
                    any(layer["viseme"] == "MBP" and layer["weight"] >= 0.999
                        for frame in frames for layer in frame["layers"]),
                    "MBP never fully closes")

    def test_window_clamping_alone_protects_the_closure(self):
        """Blending is clamped to the shorter neighbour, so even an absurd blend
        setting cannot erase a closure. Pinning is a net, not the mechanism."""
        model = dict(self.model)
        model["blend_ms"] = 400
        track = events(("A", 0.0, 0.5, "aː", "vowel"),
                       ("MBP", 0.5, 0.62, "p̚", "final"),
                       ("A", 0.62, 1.2, "aː", "vowel"))
        frames, _ = animation_lib.mouth_track(track, FPS, model)
        self.assertTrue(any(layer["viseme"] == "MBP" and layer["weight"] >= 0.999
                            for frame in frames for layer in frame["layers"]))

    def test_pin_closures_forces_a_closure_that_blending_ate(self):
        """The net itself, tested directly: given frames where MBP never reaches full
        weight, the frame nearest the closure's centre is forced to it and recorded."""
        track = events(("MBP", 0.4, 0.6, "p̚", "final"))
        frames = [{"frame": index, "time": round(0.4 + index * 0.04, 4),
                   "layers": [{"viseme": "MBP", "weight": 0.6},
                              {"viseme": "A", "weight": 0.4}]}
                  for index in range(5)]
        pinned = animation_lib.pin_closures(frames, track, self.model)
        self.assertTrue(pinned)
        self.assertTrue(pinned[0]["resolved"])
        forced = [frame for frame in frames if frame.get("closure_pinned")]
        self.assertEqual(len(forced), 1)
        self.assertEqual(forced[0]["layers"], [{"viseme": "MBP", "weight": 1.0}])

    def test_pin_closures_reports_a_closure_it_cannot_reach(self):
        """A closure falling entirely between two frames cannot be shown at all, and
        that is reported rather than passed off as fine."""
        track = events(("MBP", 0.41, 0.43, "p̚", "final"))
        frames = [{"frame": 0, "time": 0.0, "layers": [{"viseme": "A", "weight": 1.0}]},
                  {"frame": 1, "time": 1.0, "layers": [{"viseme": "A", "weight": 1.0}]}]
        pinned = animation_lib.pin_closures(frames, track, self.model)
        self.assertEqual(len(pinned), 1)
        self.assertFalse(pinned[0]["resolved"])


class ExpressionLayerTest(unittest.TestCase):
    """PLAN 8.3 and ADR-012 - the layers are independent, with one hard limit."""

    def test_expression_defaults_to_the_state(self):
        plan = plan_for()
        self.assertEqual([segment["expression"]
                          for segment in plan["tracks"]["expression"]], ["neutral"])

    def test_an_expression_plan_is_honoured(self):
        plan = plan_for(expressions=[
            {"start": 0.0, "end": 0.7, "expression": "neutral"},
            {"start": 0.7, "end": 1.5, "expression": "happy"}])
        self.assertEqual([segment["expression"]
                          for segment in plan["tracks"]["expression"]],
                         ["neutral", "happy"])

    def test_expression_and_viseme_are_independent(self):
        """The same mouth track under a different face - PLAN 8.3's happy + A."""
        neutral = plan_for()
        happy = plan_for(expressions=[{"start": 0.0, "end": 1.5,
                                       "expression": "happy"}])
        self.assertEqual([frame["layers"] for frame in neutral["tracks"]["mouth"]],
                         [frame["layers"] for frame in happy["tracks"]["mouth"]])

    def test_an_open_mouth_expression_cannot_host_a_viseme_track(self):
        """ADR-012 - the mouth is already spent; this would render two mouths."""
        for expression in sorted(canon.OPEN_MOUTH_EXPRESSIONS):
            with self.subTest(expression=expression):
                with self.assertRaises(animation_lib.AnimationError) as caught:
                    plan_for(expressions=[{"start": 0.0, "end": 1.5,
                                           "expression": expression}])
                self.assertIn("two mouths", str(caught.exception))

    def test_a_static_state_suppresses_the_viseme_track(self):
        plan = animation_lib.build(timeline_for("สวัสดีครับ", 1.5), REACTION,
                                   "reaction", FPS, generated="X")
        self.assertEqual(plan["mouth_mode"], "static")
        self.assertTrue(all(frame["layers"] == []
                            for frame in plan["tracks"]["mouth"]))

    def test_an_open_mouth_expression_is_fine_when_the_mouth_is_static(self):
        plan = animation_lib.build(timeline_for("สวัสดีครับ", 1.5), REACTION,
                                   "reaction", FPS, generated="X")
        self.assertEqual(plan["tracks"]["expression"][0]["expression"], "surprised")

    def test_a_non_canonical_expression_is_rejected(self):
        with self.assertRaises(animation_lib.AnimationError):
            plan_for(expressions=[{"start": 0.0, "end": 1.5, "expression": "smug"}])

    def test_segments_cover_the_whole_duration(self):
        plan = plan_for(expressions=[{"start": 0.4, "end": 1.0,
                                      "expression": "happy"}])
        segments = plan["tracks"]["expression"]
        self.assertAlmostEqual(segments[0]["start"], 0.0)
        self.assertAlmostEqual(segments[-1]["end"], plan["duration"], delta=0.002)


class SecondaryTest(unittest.TestCase):
    """PLAN 8.4 - and it has to be as reproducible as a seed."""

    def test_the_same_timeline_blinks_the_same_way(self):
        self.assertEqual(plan_for()["tracks"]["blink"],
                         plan_for()["tracks"]["blink"])

    def test_a_different_timeline_blinks_differently(self):
        long_a = plan_for("สวัสดีครับ ผมชื่อนารา วันนี้อากาศดีมาก", 12.0)
        long_b = plan_for("ขอบคุณมากครับ ผมเรียนภาษาไทยทุกวัน", 12.0)
        self.assertNotEqual(long_a["tracks"]["blink"], long_b["tracks"]["blink"])

    def test_blinks_stay_inside_the_duration(self):
        plan = plan_for("สวัสดีครับ ผมชื่อนารา", 10.0)
        for blink in plan["tracks"]["blink"]:
            self.assertGreaterEqual(blink["start"], 0.0)
            self.assertLessEqual(blink["end"], plan["duration"])

    def test_breath_and_sway_have_one_sample_per_frame(self):
        plan = plan_for()
        count = plan["frame_count"]
        self.assertEqual(len(plan["tracks"]["breath"]["values"]), count)
        self.assertEqual(len(plan["tracks"]["head_sway"]["x"]), count)
        self.assertEqual(len(plan["tracks"]["head_sway"]["y"]), count)

    def test_head_sway_axes_are_out_of_phase(self):
        plan = plan_for()
        sway = plan["tracks"]["head_sway"]
        self.assertNotEqual(sway["x"][:10], sway["y"][:10])

    def test_a_brow_accent_lands_on_each_expression_change(self):
        plan = plan_for(expressions=[
            {"start": 0.0, "end": 0.7, "expression": "neutral"},
            {"start": 0.7, "end": 1.5, "expression": "happy"}])
        self.assertEqual(len(plan["tracks"]["brow"]), 1)
        self.assertAlmostEqual(plan["tracks"]["brow"][0]["start"], 0.7, delta=0.002)

    def test_no_brow_accent_without_a_change(self):
        self.assertEqual(plan_for()["tracks"]["brow"], [])


class DigestTest(unittest.TestCase):

    def test_the_same_inputs_give_the_same_digest(self):
        self.assertEqual(plan_for()["digest"], plan_for()["digest"])

    def test_fps_changes_the_digest(self):
        self.assertNotEqual(plan_for(fps=25)["digest"], plan_for(fps=30)["digest"])

    def test_expression_changes_the_digest(self):
        other = plan_for(expressions=[{"start": 0.0, "end": 1.5,
                                       "expression": "happy"}])
        self.assertNotEqual(plan_for()["digest"], other["digest"])

    def test_a_rejected_fps_is_reported(self):
        with self.assertRaises(animation_lib.AnimationError):
            plan_for(fps=0)


if __name__ == "__main__":
    unittest.main()
