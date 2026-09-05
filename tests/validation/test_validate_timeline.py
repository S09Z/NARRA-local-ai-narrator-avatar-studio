#!/usr/bin/env python3
"""Tests for scripts/validation/validate_timeline.py (PHASE 7.4).

A validator that only ever passes is decoration. Every check here is exercised by
breaking a known-good timeline in exactly one way and asserting that the tool notices.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "validation" / "validate_timeline.py"

sys.path.insert(0, str(REPO / "scripts" / "lib"))
import thai_g2p                  # noqa: E402
import timeline as timeline_lib  # noqa: E402


def good_timeline(duration=1.5):
    return timeline_lib.build(thai_g2p.phonemize("สวัสดีครับ"),
                              audio_duration=duration,
                              generated="2026-08-27T00:00:00Z")


class ValidateTimelineTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.work = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, payload, reseal=False):
        if reseal:
            payload["digest"] = timeline_lib.digest(payload)
        path = self.work / "t.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def run_on(self, payload, reseal=False, *extra):
        path = self.write(payload, reseal)
        return subprocess.run([sys.executable, str(SCRIPT), str(path), *extra],
                              capture_output=True, text=True)

    # --- the good case ---------------------------------------------------------------

    def test_a_generated_timeline_is_valid(self):
        result = self.run_on(good_timeline())
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("valid", result.stdout)

    def test_unreviewed_mapping_warns_but_passes(self):
        result = self.run_on(good_timeline())
        self.assertIn("mapping/review", result.stdout)
        self.assertEqual(result.returncode, 0)

    def test_strict_turns_that_warning_into_a_failure(self):
        result = self.run_on(good_timeline(), False, "--strict")
        self.assertEqual(result.returncode, 1)

    # --- one break at a time ---------------------------------------------------------

    def test_a_gap_between_events_fails(self):
        payload = good_timeline()
        payload["events"][2]["start"] += 0.05
        result = self.run_on(payload, reseal=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("events/contiguous", result.stdout)

    def test_a_non_canonical_viseme_fails(self):
        payload = good_timeline()
        payload["events"][1]["viseme"] = "ZZ"
        result = self.run_on(payload, reseal=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("viseme/canonical", result.stdout)

    def test_adjacent_duplicates_fail(self):
        payload = good_timeline()
        payload["events"][2]["viseme"] = payload["events"][1]["viseme"]
        result = self.run_on(payload, reseal=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("viseme/no-repeats", result.stdout)

    def test_a_flicker_fails(self):
        payload = good_timeline()
        event = payload["events"][3]
        event["end"] = round(event["start"] + 0.005, 3)
        payload["events"][4]["start"] = event["end"]
        result = self.run_on(payload, reseal=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("viseme/min-duration", result.stdout)

    def test_a_hand_edited_file_fails_the_digest(self):
        payload = good_timeline()
        payload["events"][1]["viseme"] = "REST"     # edited, digest left alone
        result = self.run_on(payload, reseal=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("lock/digest", result.stdout)

    def test_duration_disagreeing_with_the_events_fails(self):
        payload = good_timeline()
        payload["duration"] = 99.0
        result = self.run_on(payload, reseal=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("events/duration", result.stdout)

    def test_an_unknown_timing_source_fails(self):
        payload = good_timeline()
        payload["timing_source"] = "vibes"
        result = self.run_on(payload, reseal=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("timing/source", result.stdout)

    def test_estimated_timing_warns(self):
        payload = timeline_lib.build(thai_g2p.phonemize("สวัสดีครับ"),
                                     generated="2026-08-27T00:00:00Z")
        result = self.run_on(payload)
        self.assertIn("timing/source", result.stdout)
        self.assertEqual(result.returncode, 0)

    def test_a_missing_field_fails(self):
        payload = good_timeline()
        del payload["idle_viseme"]
        result = self.run_on(payload, reseal=True)
        self.assertEqual(result.returncode, 1)

    def test_no_events_fails(self):
        payload = good_timeline()
        payload["events"] = []
        result = self.run_on(payload, reseal=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("events/present", result.stdout)

    def test_unreadable_file_fails(self):
        path = self.work / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        result = subprocess.run([sys.executable, str(SCRIPT), str(path)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)

    # --- audio ------------------------------------------------------------------------

    def test_a_changed_audio_file_fails(self):
        payload = good_timeline()
        payload["audio"] = {"path": str(self.work / "a.wav"),
                            "sha256": "0" * 64, "duration": 1.5,
                            "sample_rate": 22050, "channels": 1,
                            "sample_width": 2, "frames": 33075}
        sys.path.insert(0, str(REPO / "scripts" / "lib"))
        import audioinfo
        audioinfo.write_silence(self.work / "a.wav", 1.5)
        result = self.run_on(payload, reseal=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("audio/sha256", result.stdout)


if __name__ == "__main__":
    unittest.main()
