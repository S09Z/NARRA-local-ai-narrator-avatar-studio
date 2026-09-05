#!/usr/bin/env python3
"""Tests for scripts/lib/timeline.py (PHASE 7.4).

Two properties carry most of the weight. The events must tile the duration with no gap
and no overlap, because a gap is a moment where the mouth is undefined. And the times
must keep summing to the real audio length through every transformation, because they
describe audio that actually exists.
"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "lib"))
import canon         # noqa: E402
import thai_g2p      # noqa: E402
import timeline as timeline_lib  # noqa: E402

FIXED = "2026-08-27T00:00:00Z"
TOLERANCE = 0.002


def build(text, duration=None):
    return timeline_lib.build(thai_g2p.phonemize(text), audio_duration=duration,
                              generated=FIXED)


class ShapeTest(unittest.TestCase):

    def setUp(self):
        self.payload = build("สวัสดีครับ", 1.146)

    def test_matches_the_plan_74_shape(self):
        """PLAN 7.4 specifies duration plus events of start/end/phoneme/viseme."""
        self.assertIn("duration", self.payload)
        for event in self.payload["events"]:
            for field in ("start", "end", "phoneme", "viseme"):
                self.assertIn(field, event)

    def test_events_are_contiguous(self):
        events = self.payload["events"]
        self.assertAlmostEqual(events[0]["start"], 0.0, delta=TOLERANCE)
        for previous, current in zip(events, events[1:]):
            self.assertAlmostEqual(previous["end"], current["start"], delta=TOLERANCE)

    def test_events_have_positive_length(self):
        for event in self.payload["events"]:
            self.assertGreater(event["end"], event["start"])

    def test_starts_and_ends_with_rest(self):
        self.assertEqual(self.payload["events"][0]["viseme"], "REST")
        self.assertEqual(self.payload["events"][-1]["viseme"], "REST")

    def test_all_visemes_are_canonical(self):
        for event in self.payload["events"]:
            self.assertIn(event["viseme"], canon.VISEMES)


class TimingTest(unittest.TestCase):

    def test_fitting_matches_the_audio_duration(self):
        for duration in (0.8, 1.146, 3.0):
            with self.subTest(duration=duration):
                payload = build("สวัสดีครับ", duration)
                self.assertEqual(payload["timing_source"], timeline_lib.FITTED)
                self.assertAlmostEqual(payload["duration"], duration, delta=TOLERANCE)
                self.assertAlmostEqual(payload["events"][-1]["end"], duration,
                                       delta=TOLERANCE)

    def test_without_audio_the_timing_is_labelled_estimated(self):
        payload = build("สวัสดีครับ")
        self.assertEqual(payload["timing_source"], timeline_lib.ESTIMATED)

    def test_longer_text_estimates_longer(self):
        short = build("นารา")["duration"]
        long = build("นารานารานารานารา")["duration"]
        self.assertGreater(long, short)

    def test_absorbing_a_silent_phoneme_does_not_lose_its_time(self):
        """/h/ has no shape, but it still takes time in the audio."""
        payload = build("หาน", 1.0)
        self.assertAlmostEqual(payload["events"][-1]["end"], 1.0, delta=TOLERANCE)


class FlickerTest(unittest.TestCase):
    """mapping.md section 6 - a viseme held one frame reads as a flicker."""

    def test_no_event_is_shorter_than_the_minimum(self):
        minimum = timeline_lib.load_model()["min_viseme_duration_s"]
        for text, duration in [("สวัสดีครับ", 1.146), ("กรุงเทพมหานคร", 2.0),
                               ("ขอบคุณมาก", 0.9)]:
            payload = build(text, duration)
            for event in payload["events"]:
                with self.subTest(text=text, viseme=event["viseme"]):
                    self.assertGreaterEqual(event["end"] - event["start"],
                                            minimum - TOLERANCE)

    def test_absorbed_events_are_recorded_not_hidden(self):
        payload = build("สวัสดีครับ", 1.146)
        self.assertTrue(payload["absorbed_events"])
        for entry in payload["absorbed_events"]:
            self.assertIn("viseme", entry)

    def test_squeezing_the_audio_keeps_the_total(self):
        payload = build("กรุงเทพมหานคร", 0.5)
        self.assertAlmostEqual(payload["events"][-1]["end"], 0.5, delta=TOLERANCE)


class MergeTest(unittest.TestCase):

    def test_no_adjacent_duplicate_visemes(self):
        for text in ("สวัสดีครับ", "กรุงเทพมหานคร", "เรียนภาษาไทย", "ขอบคุณมาก"):
            payload = build(text, 2.0)
            visemes = [event["viseme"] for event in payload["events"]]
            for previous, current in zip(visemes, visemes[1:]):
                with self.subTest(text=text):
                    self.assertNotEqual(previous, current)


class DigestTest(unittest.TestCase):
    """Reproducibility, the way seeds work for images (CLAUDE.md)."""

    def test_same_input_same_digest(self):
        self.assertEqual(build("สวัสดีครับ", 1.146)["digest"],
                         build("สวัสดีครับ", 1.146)["digest"])

    def test_digest_ignores_the_timestamp(self):
        first = timeline_lib.build(thai_g2p.phonemize("นารา"), generated="2020-01-01T00:00:00Z")
        second = timeline_lib.build(thai_g2p.phonemize("นารา"), generated="2026-08-27T00:00:00Z")
        self.assertEqual(first["digest"], second["digest"])

    def test_different_text_different_digest(self):
        self.assertNotEqual(build("นารา", 1.0)["digest"], build("นาริ", 1.0)["digest"])

    def test_different_timing_different_digest(self):
        self.assertNotEqual(build("นารา", 1.0)["digest"], build("นารา", 2.0)["digest"])


class ProvenanceTest(unittest.TestCase):
    """CLAUDE.md Reproducibility - a locked artefact records what made it."""

    def test_records_its_inputs(self):
        payload = build("สวัสดีครับ", 1.146)
        self.assertEqual(payload["g2p"]["engine"], "builtin")
        self.assertEqual(payload["g2p"]["ipa"], "sa wat̚ diː kʰrap̚")
        self.assertIsNotNone(payload["viseme_map"]["version"])
        self.assertIsNotNone(payload["duration_model"]["version"])

    def test_carries_the_unreviewed_mapping_warning(self):
        payload = build("นารา", 1.0)
        self.assertFalse(payload["viseme_map"]["reviewed_by_thai_speaker"])


if __name__ == "__main__":
    unittest.main()
