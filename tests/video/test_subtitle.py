#!/usr/bin/env python3
"""Tests for scripts/lib/subtitle.py (PHASE 9).

The contract that matters is that a cue shows the sentence that was spoken, broken
where a word ends. Thai makes both parts easy to get wrong and hard to notice: tone
marks are stripped for phonemization and must come back for display, and a line
break at a character count lands inside a word.

Run:
    python3 -m unittest discover -s tests -p 'test_*.py' -v
"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "lib"))
sys.path.insert(0, str(REPO / "tests"))

import subtitle                                       # noqa: E402
from video import fixtures                            # noqa: E402


class WordsTest(unittest.TestCase):

    def test_display_text_keeps_its_tone_marks(self):
        """วันนี้ is a word; วันนี is a different one. Phonemization strips the mark."""
        payload = fixtures.timeline()
        texts = [word["text"] for word in subtitle.words(payload)]
        self.assertIn("วันนี้", texts)
        self.assertNotIn("วันนี", texts)
        self.assertIn("รู้", texts)

    def test_karan_survives_into_the_display_text(self):
        payload = fixtures.timeline("สตางค์", duration=1.0)
        joined = "".join(word["text"] for word in subtitle.words(payload))
        self.assertIn("ค์", joined)

    def test_adjacent_identical_words_stay_separate(self):
        """Grouping by text alone would collapse มามา into one word."""
        payload = fixtures.timeline("มามา", duration=1.0)
        words = subtitle.words(payload)
        self.assertEqual([word["text"] for word in words], ["มา", "มา"])

    def test_words_are_ordered_and_timed(self):
        words = subtitle.words(fixtures.timeline())
        for word in words:
            self.assertIsNotNone(word["start"])
            self.assertIsNotNone(word["end"])
            self.assertLessEqual(word["start"], word["end"])
        for before, after in zip(words, words[1:]):
            self.assertLessEqual(before["span"][1], after["span"][0])

    def test_syllable_count_mismatch_is_refused(self):
        payload = fixtures.timeline()
        payload["g2p"]["syllables"] += 3
        with self.assertRaises(subtitle.SubtitleError) as caught:
            subtitle.words(payload)
        self.assertIn("syllables", str(caught.exception))

    def test_missing_text_is_refused(self):
        payload = fixtures.timeline()
        payload["text"] = ""
        with self.assertRaises(subtitle.SubtitleError):
            subtitle.words(payload)


class CueTest(unittest.TestCase):

    def setUp(self):
        self.payload = fixtures.timeline()
        self.style = subtitle.load_style()
        self.cues = subtitle.cues(self.payload)

    def test_cues_cover_the_sentence(self):
        joined = "".join(cue["text"].replace("\n", "") for cue in self.cues)
        for word in ("สวัสดี", "อาหาร", "ไทย"):
            self.assertIn(word, joined)

    def test_cues_break_at_a_pause(self):
        """The sentence has one break, after ครับ; a cue should end there."""
        self.assertGreater(len(self.cues), 1)
        self.assertTrue(self.cues[0]["text"].endswith("ครับ"))

    def test_cues_are_ordered_and_do_not_overlap(self):
        for before, after in zip(self.cues, self.cues[1:]):
            self.assertLessEqual(before["end"], after["start"] + 1e-9)
            self.assertLess(before["start"], before["end"])

    def test_cues_respect_the_layout(self):
        layout = self.style["layout"]
        for cue in self.cues:
            self.assertLessEqual(len(cue["lines"]), layout["max_lines"])
            for line in cue["lines"]:
                self.assertLessEqual(len(line), layout["max_characters_per_line"])

    def test_cues_stay_inside_the_audio(self):
        for cue in self.cues:
            self.assertLessEqual(cue["end"], self.payload["duration"] + 1e-6)

    def test_a_long_sentence_wraps_onto_two_lines(self):
        long_text = "วันนี้เราจะมาเรียนรู้เรื่องการทำอาหารไทยแบบง่ายๆ ที่ทุกคนทำตามได้ที่บ้าน"
        cues = subtitle.cues(fixtures.timeline(long_text, duration=9.0))
        self.assertTrue(any(len(cue["lines"]) == 2 for cue in cues))
        for cue in cues:
            self.assertLessEqual(len(cue["lines"]), 2)

    def test_short_cue_is_held_to_the_minimum(self):
        cues = subtitle.cues(fixtures.timeline("ครับ", duration=3.0))
        self.assertGreaterEqual(cues[0]["end"] - cues[0]["start"],
                                self.style["reading"]["min_duration_s"] - 1e-6)

    def test_reading_speed_is_recorded_not_hidden(self):
        for cue in self.cues:
            self.assertIn("reading_speed_cps", cue)
            self.assertIn("too_fast", cue)
            self.assertGreater(cue["reading_speed_cps"], 0)

    def test_empty_text_yields_no_cues(self):
        payload = fixtures.timeline("   ", duration=1.0)
        self.assertEqual(subtitle.cues(payload), [])


class SerialisationTest(unittest.TestCase):

    def setUp(self):
        self.cues = subtitle.cues(fixtures.timeline())

    def test_srt_shape(self):
        body = subtitle.to_srt(self.cues)
        blocks = [block for block in body.split("\n\n") if block.strip()]
        self.assertEqual(len(blocks), len(self.cues))
        first = blocks[0].splitlines()
        self.assertEqual(first[0], "1")
        self.assertRegex(first[1], r"^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}$")

    def test_srt_time_formatting(self):
        self.assertEqual(subtitle._srt_time(0), "00:00:00,000")
        self.assertEqual(subtitle._srt_time(3661.5), "01:01:01,500")
        self.assertEqual(subtitle._ass_time(3661.5), "1:01:01.50")

    def test_ass_carries_playres_and_dialogue(self):
        body = subtitle.to_ass(self.cues, canvas={"width": 1920, "height": 1080})
        self.assertIn("PlayResX: 1920", body)
        self.assertIn("PlayResY: 1080", body)
        self.assertEqual(body.count("Dialogue:"), len(self.cues))

    def test_ass_encodes_line_breaks_as_backslash_n(self):
        cues = [{"index": 1, "start": 0.0, "end": 2.0, "text": "หนึ่ง\nสอง"}]
        body = subtitle.to_ass(cues)
        self.assertIn("หนึ่ง\\Nสอง", body)
        self.assertNotIn("หนึ่ง\nสอง", body.split("[Events]")[1])

    def test_ass_colour_is_converted_to_ass_byte_order(self):
        body = subtitle.to_ass(self.cues)
        self.assertIn("&H00FFFFFF", body)              # white, BGR with a leading alpha


class StyleTest(unittest.TestCase):

    def test_style_loads_and_carries_its_sources(self):
        style = subtitle.load_style()
        self.assertEqual(style["language"], "th")
        self.assertIn("source", style["reading"])
        self.assertEqual(style["layout"]["break_policy"], "syllable")

    def test_unreadable_style_is_refused(self):
        with self.assertRaises(subtitle.SubtitleError):
            subtitle.load_style(REPO / "docs" / "video" / "not-a-file.json")

    def test_find_font_returns_none_when_nothing_is_installed(self):
        style = {"style": {"font_files": ["/nowhere/none.ttf"]}}
        self.assertIsNone(subtitle.find_font(style))


if __name__ == "__main__":
    unittest.main()
