#!/usr/bin/env python3
"""Tests for scripts/lib/viseme_map.py (PHASE 7.3).

The test that matters here is the last one: the markdown table in
docs/thai-viseme/thai-viseme-mapping.md and the JSON in thai-viseme-map.json are the
same mapping written twice, and two copies of a mapping drift. The prose is what a Thai
speaker will review; the JSON is what the animation is built from. If they disagree,
the review does not apply to the animation.
"""

import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "lib"))
import canon         # noqa: E402
import thai_g2p      # noqa: E402
import viseme_map    # noqa: E402

DOC = REPO / "docs" / "thai-viseme" / "thai-viseme-mapping.md"

IPA_CELL = re.compile(r"^/(.+)/$")
VISEME_CELL = re.compile(r"`([A-Z]+)`")

# Section heading -> the JSON section its rows belong to. Sections 4 and 5 are keyed by
# orthography and by viseme respectively, so they are not phoneme rows at all.
SECTIONS = {
    "## 1. Initial consonants": "initial",
    "## 2. Vowels": "vowel",
    "### Diphthongs": "diphthong",
    "### Vowel + glide sequences": "glide",
    "## 3. Final consonants": "final",
}


def doc_rows():
    """(section, [phonemes], [visemes]) for every phoneme row in the markdown."""
    section = None
    rows = []
    for line in DOC.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped in SECTIONS:
            section = SECTIONS[stripped]
            continue
        if stripped.startswith("##"):
            section = None
            continue
        if section is None or not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        ipa_cell = next((cell for cell in cells if IPA_CELL.match(cell)), None)
        if not ipa_cell:
            continue
        phonemes = IPA_CELL.match(ipa_cell).group(1).split()
        index = cells.index(ipa_cell)
        viseme_cell = cells[index + 1] if index + 1 < len(cells) else ""
        visemes = VISEME_CELL.findall(viseme_cell)
        rows.append((section, phonemes, visemes, "*(none)*" in viseme_cell))
    return rows


class MappingFileTest(unittest.TestCase):

    def setUp(self):
        self.mapping = viseme_map.load()

    def test_every_viseme_is_canonical(self):
        """A mapping that names a shape outside the set points at an asset that
        cannot exist - lock_library.py would never have generated it."""
        self.assertEqual(self.mapping["viseme_set"], canon.VISEMES)
        for section in ("initial", "final", "vowel", "loanword"):
            for phoneme, viseme in self.mapping[section].items():
                with self.subTest(section=section, phoneme=phoneme):
                    if viseme is not None:
                        self.assertIn(viseme, canon.VISEMES)
        for phoneme, visemes in self.mapping["diphthong"].items():
            for viseme in visemes:
                self.assertIn(viseme, canon.VISEMES)

    def test_silence_is_rest(self):
        self.assertEqual(viseme_map.silence(), "REST")

    def test_invisible_phonemes_map_to_nothing(self):
        """mapping.md section 1 - /h/ and /ʔ/ have no visible articulation."""
        self.assertEqual(viseme_map.viseme_for("h", "initial"), [])
        self.assertEqual(viseme_map.viseme_for("ʔ", "initial"), [])

    def test_bilabials_collapse(self):
        """mapping.md section 5 - and MBP must be distinct from REST (CLAUDE.md)."""
        for phoneme in ("b", "p", "pʰ", "m"):
            self.assertEqual(viseme_map.viseme_for(phoneme, "initial"), ["MBP"])

    def test_diphthongs_are_two_shapes(self):
        for phoneme in ("ia", "ɨa", "ua"):
            self.assertEqual(len(viseme_map.viseme_for(phoneme, "vowel")), 2)

    def test_th_is_not_used_for_native_thai(self):
        """mapping.md section 5 - Thai has no interdental. TH is loanword-only."""
        native = set(self.mapping["initial"].values()) | set(self.mapping["final"].values())
        native |= set(self.mapping["vowel"].values())
        self.assertNotIn("TH", native)
        self.assertEqual(self.mapping["loanword"]["θ"], "TH")


class CoverageTest(unittest.TestCase):
    """Everything the G2P can emit must have somewhere to go."""

    def test_every_g2p_phoneme_is_mapped(self):
        emitted = set(thai_g2p.INITIAL_IPA.values()) | set(thai_g2p.FINAL_IPA.values())
        emitted |= set(thai_g2p.VOWEL_PHONEMES)
        emitted |= set(thai_g2p.IRREGULAR_INITIALS.values())
        self.assertEqual(viseme_map.unmapped_phonemes(emitted), [])

    def test_corpus_produces_only_canonical_visemes(self):
        for text in ("สวัสดีครับ", "ขอบคุณมาก", "กรุงเทพมหานคร", "เรียนภาษาไทย"):
            result = thai_g2p.phonemize(text)
            for phone in result.phones:
                for viseme in viseme_map.viseme_for(phone.symbol, phone.role):
                    self.assertIn(viseme, canon.VISEMES)


class DocumentationAgreementTest(unittest.TestCase):
    """DECISIONS.md ADR-019 - the prose and the data are one mapping, checked."""

    def setUp(self):
        self.mapping = viseme_map.load()
        self.rows = doc_rows()

    def test_the_markdown_has_rows_to_check(self):
        self.assertGreater(len(self.rows), 40, "the table parser found almost nothing")

    def test_json_agrees_with_the_markdown(self):
        for section, phonemes, visemes, is_none in self.rows:
            for phoneme in phonemes:
                with self.subTest(section=section, phoneme=phoneme):
                    if section == "glide":
                        # Written as a vowel row, stored as vowel plus final glide.
                        vowel, glide = phoneme[:-1], phoneme[-1]
                        self.assertEqual([self.mapping["vowel"][vowel]], visemes[:1])
                        self.assertEqual([self.mapping["final"][glide]], visemes[1:])
                    elif section == "diphthong":
                        self.assertEqual(self.mapping["diphthong"][phoneme], visemes)
                    elif is_none:
                        self.assertIsNone(self.mapping[section][phoneme])
                    else:
                        self.assertEqual([self.mapping[section][phoneme]], visemes)

    def test_markdown_covers_every_json_entry(self):
        documented = set()
        for section, phonemes, _, _ in self.rows:
            for phoneme in phonemes:
                if section == "glide":
                    documented.add(phoneme[:-1])
                    documented.add(phoneme[-1])
                else:
                    documented.add(phoneme)
        for section in ("initial", "final", "vowel", "diphthong"):
            for phoneme in self.mapping[section]:
                with self.subTest(section=section, phoneme=phoneme):
                    self.assertIn(phoneme, documented,
                                  f"{phoneme} is in the JSON but not in the markdown")


if __name__ == "__main__":
    unittest.main()
