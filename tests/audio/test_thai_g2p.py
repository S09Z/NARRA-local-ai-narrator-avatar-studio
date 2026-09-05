#!/usr/bin/env python3
"""Tests for scripts/lib/thai_g2p.py (PHASE 7.2).

The corpus below is the contract. Thai G2P without a pronunciation dictionary has a
real ceiling, and the only honest way to hold a rule parser to account is to write down
what it is expected to produce and notice when that changes.
"""

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "lib"))
import thai_g2p  # noqa: E402

# Word -> expected IPA, syllables separated by spaces. Verified by hand against the
# standard readings; several only come out right because of the exception lexicon.
CORPUS = {
    "สวัสดีครับ": "sa wat̚ diː kʰrap̚",
    "ผมชื่อนารา": "pʰom tɕʰɨː naː raː",
    "ทำงาน": "tʰam ŋaːn",
    "คนไทย": "kʰon tʰaj",
    "ประเทศไทย": "pra tʰeːt̚ tʰaj",
    "เดินทาง": "dəːn tʰaːŋ",
    "น้ำใจ": "nam tɕaj",
    "สตางค์": "sa taːŋ",
    "ขอบคุณมาก": "kʰɔːp̚ kʰun maːk̚",
    "ความรู้": "kʰwaːm ruː",
    "เรียนภาษาไทย": "rian pʰaː saː tʰaj",
    "อาหารอร่อย": "ʔaː haːn ʔa rɔːj",
    "กรุงเทพมหานคร": "kruŋ tʰeːp̚ ma haː na kʰɔːn",
    "วันนี้อากาศดี": "wan niː ʔaː kaːt̚ diː",
}


class CorpusTest(unittest.TestCase):

    def test_corpus_parses_as_expected(self):
        for text, expected in CORPUS.items():
            with self.subTest(text=text):
                self.assertEqual(thai_g2p.phonemize(text).ipa, expected)

    def test_corpus_is_fully_covered(self):
        for text in CORPUS:
            with self.subTest(text=text):
                self.assertEqual(thai_g2p.phonemize(text).coverage, 1.0)
                self.assertEqual(thai_g2p.phonemize(text).unparsed, [])


class ToneTest(unittest.TestCase):
    """mapping.md section 0 - all five tones share one articulation."""

    def test_tone_marks_do_not_change_phonemes(self):
        self.assertEqual(thai_g2p.phonemize("นา").ipa, thai_g2p.phonemize("น่า").ipa)
        self.assertEqual(thai_g2p.phonemize("นา").ipa, thai_g2p.phonemize("น้า").ipa)

    def test_strip_tones_removes_only_tone_marks(self):
        self.assertEqual(thai_g2p.strip_tones("น้ำ"), "นำ")
        self.assertEqual(thai_g2p.strip_tones("สวัสดี"), "สวัสดี")


class OrthographyTest(unittest.TestCase):

    def test_karan_silences_its_consonant(self):
        self.assertEqual(thai_g2p.apply_karan("สตางค์"), "สตาง")

    def test_repeat_mark_repeats_the_previous_syllable(self):
        self.assertEqual(thai_g2p.phonemize("ต่างๆ").ipa, "taːŋ taːŋ")

    def test_leading_ho_hip_is_silent(self):
        # หมา is /maː/, not /hamaː/ - the ho hip marks tone, not a sound.
        self.assertEqual(thai_g2p.phonemize("หมา").ipa, "maː")

    def test_o_leading_is_silent(self):
        self.assertEqual(thai_g2p.phonemize("อยาก").ipa, "jaːk̚")

    def test_irregular_initial(self):
        self.assertEqual(thai_g2p.phonemize("ทราย").ipa, "saːj")

    def test_finals_neutralise(self):
        """mapping.md section 3 - many letters, one closure."""
        for word, final in [("บาป", "p̚"), ("บาท", "t̚"), ("บาง", "ŋ")]:
            with self.subTest(word=word):
                self.assertEqual(thai_g2p.phonemize(word).syllables[0].final, final)


class ClusterAmbiguityTest(unittest.TestCase):
    """The case greedy matching gets wrong, and the reason the parse is scored."""

    def test_cluster_onset_beats_coda(self):
        result = thai_g2p.phonemize("ดีครับ")
        self.assertEqual(result.ipa, "diː kʰrap̚")

    def test_cluster_is_two_initials(self):
        syllable = thai_g2p.phonemize("ครับ").syllables[0]
        self.assertEqual(syllable.initial, ["kʰ", "r"])


class LexiconTest(unittest.TestCase):

    def test_parse_ipa_syllable_handles_clusters(self):
        self.assertEqual(thai_g2p.parse_ipa_syllable("kʰrap̚"), (["kʰ", "r"], "a", "p̚"))

    def test_parse_ipa_syllable_without_final(self):
        self.assertEqual(thai_g2p.parse_ipa_syllable("naː"), (["n"], "aː", None))

    def test_parse_ipa_syllable_rejects_nonsense(self):
        with self.assertRaises(thai_g2p.LexiconError):
            thai_g2p.parse_ipa_syllable("xyz")

    def test_shipped_lexicon_loads(self):
        entries = thai_g2p.load_lexicon()
        self.assertGreater(len(entries), 0)

    def test_lexicon_entry_overrides_the_rules(self):
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "lex.json"
            path.write_text('{"words": {"นารา": ["niː", "roː"]}}', encoding="utf-8")
            entries = thai_g2p.load_lexicon(path)
            _, parsed, _ = thai_g2p._best_parse("นารา", entries)
            syllables = thai_g2p._build_syllables("นารา", parsed, 0)
            self.assertEqual(" ".join(s.ipa for s in syllables), "niː roː")


class ReportingTest(unittest.TestCase):
    """Anything unparsed must be reported, never silently dropped."""

    def test_non_thai_is_not_counted_against_coverage(self):
        result = thai_g2p.phonemize("นารา 2026")
        self.assertEqual(result.coverage, 1.0)

    def test_phrase_breaks_are_recorded(self):
        result = thai_g2p.phonemize("นารา นารา")
        self.assertTrue(result.breaks)

    def test_phones_carry_roles(self):
        phones = thai_g2p.phonemize("นาน").phones
        self.assertEqual([p.role for p in phones], ["initial", "vowel", "final"])

    def test_unknown_engine_raises(self):
        with self.assertRaises(ValueError):
            thai_g2p.phonemize("นารา", engine="nope")


if __name__ == "__main__":
    unittest.main()
