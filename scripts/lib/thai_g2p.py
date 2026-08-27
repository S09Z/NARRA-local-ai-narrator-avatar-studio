"""Thai grapheme-to-phoneme - text to IPA phonemes, for the viseme timeline (PHASE 7.2).

PLAN 7.2 asks for a Thai-compatible phoneme approach to be researched and selected.
The selection is recorded in DECISIONS.md ADR-021: an external engine (pythainlp) is
preferred when installed, and this module is the zero-dependency fallback that keeps the
pipeline runnable and testable without one. Both go through `phonemize()`.

What this is: a rule-based orthographic parser for standard Thai spelling. It segments
a string into syllables by matching Thai vowel patterns, then reads each syllable's
initial, vowel, and final off the match.

What this is not: a pronunciation dictionary. Thai spelling underdetermines pronunciation
in ways no rule can fix - loanwords, silent letters beyond karan, irregular readings, and
compound words that resyllabify. Anything unparsed is REPORTED, never guessed at
silently: see `G2PResult.unparsed` and `--report` on build_timeline.py.

Tone marks are stripped before parsing. docs/thai-viseme/thai-viseme-mapping.md section 0
establishes that all five Thai tones share one articulation, so tone cannot change a
mouth shape. It matters for duration, which is the timing model's problem, not this one.

Not a package (DECISIONS.md ADR-007, ADR-011). Importers do:

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
    import thai_g2p
"""

import json
import re
import unicodedata
from pathlib import Path

# --- Thai codepoint classes (Unicode block U+0E00-U+0E7F) ----------------------------

TONE_MARKS = "่้๊๋"       # mai ek, tho, tri, chattawa
KARAN = "์"                               # thanthakhat - silences its consonant
REPEAT = "ๆ"                              # mai yamok - repeat previous syllable
PAIYANNOI = "ฯ"                           # abbreviation mark
CONSONANT_RANGE = "ก-ฮ"

# ASSET_SPEC has no say here; these come from Thai orthography itself.
INITIAL_IPA = {
    "ก": "k",
    "ข": "kʰ", "ฃ": "kʰ", "ค": "kʰ", "ฅ": "kʰ", "ฆ": "kʰ",
    "ง": "ŋ",
    "จ": "tɕ",
    "ฉ": "tɕʰ", "ช": "tɕʰ", "ฌ": "tɕʰ",
    "ซ": "s", "ศ": "s", "ษ": "s", "ส": "s",
    "ญ": "j", "ย": "j",
    "ฎ": "d", "ด": "d",
    "ฏ": "t", "ต": "t",
    "ฐ": "tʰ", "ฑ": "tʰ", "ฒ": "tʰ", "ถ": "tʰ", "ท": "tʰ", "ธ": "tʰ",
    "ณ": "n", "น": "n",
    "บ": "b",
    "ป": "p",
    "ผ": "pʰ", "พ": "pʰ", "ภ": "pʰ",
    "ฝ": "f", "ฟ": "f",
    "ม": "m",
    "ร": "r",
    "ล": "l", "ฬ": "l",
    "ว": "w",
    "ห": "h", "ฮ": "h",
    "อ": "ʔ",
}

# Finals neutralise: mapping.md section 3 - "drive the mapping from pronunciation, not
# orthography". Eleven different letters all close as an unreleased /t/.
FINAL_IPA = {
    "บ": "p̚", "ป": "p̚", "พ": "p̚", "ฟ": "p̚", "ภ": "p̚",
    "ด": "t̚", "ต": "t̚", "ถ": "t̚", "ท": "t̚", "ธ": "t̚", "ส": "t̚",
    "ช": "t̚", "จ": "t̚", "ศ": "t̚", "ษ": "t̚", "ซ": "t̚", "ฎ": "t̚",
    "ฏ": "t̚", "ฐ": "t̚", "ฑ": "t̚", "ฒ": "t̚", "ฌ": "t̚",
    "ก": "k̚", "ข": "k̚", "ค": "k̚", "ฆ": "k̚",
    "ม": "m",
    "น": "n", "ญ": "n", "ณ": "n", "ร": "n", "ล": "n", "ฬ": "n",
    "ง": "ŋ",
    "ว": "w",
    "ย": "j",
}

# mapping.md section 4. Written as orthography because that is what the parser sees.
CLUSTERS = [
    "กร", "กล", "กว", "ขร", "ขล", "ขว", "คร", "คล", "คว",
    "ปร", "ปล", "ผล", "พร", "พล", "ตร",
    "บร", "บล", "ดร", "ฟร", "ฟล", "ฟว",       # loanword clusters
]

# Orthographic initials that do not decompose regularly. ทราย is /saːj/, not /tʰraːj/.
IRREGULAR_INITIALS = {"ทร": "s", "สร": "s", "ศร": "s"}

# A leading ห before a low-class sonorant is a tone device: the ห is silent and the
# second consonant is the real initial. Same for อ in the four อย- words.
H_LEADING = "ห[งญณนมยรลฬว]"
O_LEADING = "อย"

FINAL_CHARS = "".join(sorted(set(FINAL_IPA)))

# --- Syllable patterns ---------------------------------------------------------------
# Ordered longest-first within each leading form. {I} is the initial, {F} a final.
# `ipa` is (vowel, extra_final) - extra_final is a glide the vowel form implies.

C = f"[{CONSONANT_RANGE}]"
INIT = (f"(?P<i>{H_LEADING}|{O_LEADING}|"
        + "|".join(CLUSTERS) + "|" + "|".join(IRREGULAR_INITIALS) + f"|{C})")
FIN = f"(?P<f>[{FINAL_CHARS}])"

_PATTERNS = [
    # leading vowel เ
    ("เ" + INIT + "ียะ",        "ia",  None),
    ("เ" + INIT + "ีย" + FIN,   "ia",  None),
    ("เ" + INIT + "ีย",          "ia",  None),
    ("เ" + INIT + "ือะ",        "ɨa",  None),
    ("เ" + INIT + "ือ" + FIN,   "ɨa",  None),
    ("เ" + INIT + "ือ",          "ɨa",  None),
    ("เ" + INIT + "าะ",         "ɔ",   None),
    ("เ" + INIT + "อะ",         "ə",   None),
    ("เ" + INIT + "ิ" + FIN,    "əː",  None),
    ("เ" + INIT + "อ" + FIN,    "əː",  None),
    ("เ" + INIT + "อ",           "əː",  None),
    ("เ" + INIT + "็" + FIN,    "e",   None),
    ("เ" + INIT + "ะ",           "e",   None),
    ("เ" + INIT + "า",           "a",   "w"),      # /aw/ - vowel plus glide
    ("เ" + INIT + FIN,            "eː",  None),
    ("เ" + INIT,                  "eː",  None),
    # leading vowel แ
    ("แ" + INIT + "ะ",           "ɛ",   None),
    ("แ" + INIT + "็" + FIN,    "ɛ",   None),
    ("แ" + INIT + FIN,            "ɛː",  None),
    ("แ" + INIT,                  "ɛː",  None),
    # leading vowel โ
    ("โ" + INIT + "ะ",           "o",   None),
    ("โ" + INIT + FIN,            "oː",  None),
    ("โ" + INIT,                  "oː",  None),
    # leading vowels ใ ไ - both /aj/
    ("ใ" + INIT,                  "a",   "j"),
    ("ไ" + INIT + "ย",           "a",   "j"),
    ("ไ" + INIT,                  "a",   "j"),
    # in-line and trailing vowels
    (INIT + "ัวะ",               "ua",  None),
    (INIT + "ัว" + FIN,          "ua",  None),
    (INIT + "ัว",                 "ua",  None),
    (INIT + "ำ",                  "a",   "m"),
    (INIT + "ัย",                 "a",   "j"),
    (INIT + "ั" + FIN,           "a",   None),
    (INIT + "ะ",                  "a",   None),
    (INIT + "า" + FIN,           "aː",  None),
    (INIT + "า",                  "aː",  None),
    (INIT + "ิ" + FIN,           "i",   None),
    (INIT + "ิ",                  "i",   None),
    (INIT + "ี" + FIN,           "iː",  None),
    (INIT + "ี",                  "iː",  None),
    (INIT + "ึ" + FIN,           "ɨ",   None),
    (INIT + "ึ",                  "ɨ",   None),
    (INIT + "ือ" + FIN,          "ɨː",  None),
    (INIT + "ือ",                 "ɨː",  None),
    (INIT + "ื" + FIN,           "ɨː",  None),
    (INIT + "ุ" + FIN,           "u",   None),
    (INIT + "ุ",                  "u",   None),
    (INIT + "ู" + FIN,           "uː",  None),
    (INIT + "ู",                  "uː",  None),
    (INIT + "อ" + FIN,           "ɔː",  None),
    (INIT + "อ",                  "ɔː",  None),
    (INIT + "็",                  "ɔː",  None),      # ก็
    (INIT + "ว" + FIN,           "ua",  None),      # สวน
    # no written vowel: inherent /o/ with a final, bare initial otherwise
    (INIT + FIN,                  "o",   None),
    (INIT,                        "a",   None),
]

def _kind(pattern):
    """Whether the syllable wrote its vowel down, or we inferred it."""
    if pattern == INIT:
        return "inherent_a"
    if pattern == INIT + FIN:
        return "inherent_o"
    return "written"


COMPILED = [(re.compile(pattern), vowel, glide, _kind(pattern))
            for pattern, vowel, glide in _PATTERNS]


class Phone:
    """One phoneme with the role it plays in its syllable."""

    __slots__ = ("symbol", "role", "syllable")

    def __init__(self, symbol, role, syllable):
        self.symbol = symbol
        self.role = role              # initial | vowel | final
        self.syllable = syllable      # index into G2PResult.syllables

    def __repr__(self):
        return f"Phone({self.symbol!r}, {self.role!r})"

    def __eq__(self, other):
        return (isinstance(other, Phone) and self.symbol == other.symbol
                and self.role == other.role and self.syllable == other.syllable)


class Syllable:
    """A parsed Thai syllable and the phonemes read off it."""

    __slots__ = ("text", "initial", "vowel", "final", "index")

    def __init__(self, text, initial, vowel, final, index):
        self.text = text
        self.initial = initial        # list of IPA strings (a cluster has two)
        self.vowel = vowel
        self.final = final            # IPA string or None
        self.index = index

    @property
    def ipa(self):
        return "".join(self.initial) + self.vowel + (self.final or "")

    def phones(self):
        out = [Phone(symbol, "initial", self.index) for symbol in self.initial]
        out.append(Phone(self.vowel, "vowel", self.index))
        if self.final:
            out.append(Phone(self.final, "final", self.index))
        return out

    def __repr__(self):
        return f"Syllable({self.text!r} -> /{self.ipa}/)"


class G2PResult:
    """Syllables, phones, and an honest record of what could not be parsed."""

    def __init__(self, text, syllables, unparsed, breaks):
        self.text = text
        self.syllables = syllables
        self.unparsed = unparsed      # list of (position, character)
        self.breaks = breaks          # syllable indices after which a pause falls

    @property
    def phones(self):
        out = []
        for syllable in self.syllables:
            out.extend(syllable.phones())
        return out

    @property
    def ipa(self):
        return " ".join(syllable.ipa for syllable in self.syllables)

    @property
    def coverage(self):
        """Fraction of Thai characters that landed inside a syllable."""
        thai = sum(1 for ch in self.text if is_thai(ch))
        if not thai:
            return 1.0
        return (thai - len(self.unparsed)) / thai


def is_thai(ch):
    return "ก" <= ch <= "๛"


def strip_tones(text):
    """Remove tone marks. mapping.md section 0 - tone does not change mouth shape."""
    return "".join(ch for ch in text if ch not in TONE_MARKS)


def apply_karan(text):
    """Delete each consonant silenced by thanthakhat, and the mark itself.

    สตางค์ -> สตาง. The karan kills the consonant it sits on; a preceding cluster
    member (as in ...รค์) goes with it.
    """
    out = []
    for ch in text:
        if ch == KARAN:
            while out and not is_thai(out[-1]):
                out.pop()
            if out:
                out.pop()
            continue
        out.append(ch)
    return "".join(out)


def expand_repeats(text):
    """Mai yamok repeats the preceding syllable: ต่างๆ -> ต่างต่าง."""
    if REPEAT not in text:
        return text
    out = []
    for ch in text:
        if ch != REPEAT:
            out.append(ch)
            continue
        tail = "".join(out)
        parsed = _parse_run(tail)
        if parsed:
            out.append(parsed[-1].text)
    return "".join(out)


def normalise(text):
    """Everything that happens before a single pattern is tried."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace(PAIYANNOI, " ")
    text = strip_tones(text)
    text = apply_karan(text)
    return expand_repeats(text)


SONORANTS = "งญณนมยรลฬว"

# --- Exception lexicon ---------------------------------------------------------------
# Where the rules cannot decide, a listed pronunciation decides for them. See
# docs/audio/thai-lexicon.json and DECISIONS.md ADR-020.

DEFAULT_LEXICON = (Path(__file__).resolve().parents[2]
                   / "docs" / "audio" / "thai-lexicon.json")

INITIAL_PHONEMES = sorted(set(INITIAL_IPA.values()), key=len, reverse=True)
FINAL_PHONEMES = sorted(set(FINAL_IPA.values()), key=len, reverse=True)
VOWEL_PHONEMES = sorted(
    ["ia", "ɨa", "ua",
     "aː", "ɛː", "eː", "iː", "ɨː", "uː", "oː", "ɔː", "əː",
     "a", "ɛ", "e", "i", "ɨ", "u", "o", "ɔ", "ə"],
    key=len, reverse=True)


class LexiconError(Exception):
    """A lexicon entry is not a syllable this phoneme inventory can express."""


def parse_ipa_syllable(ipa):
    """Split an IPA syllable into (initials, vowel, final).

    The lexicon stores syllables the way a person would write them - "kʰrap̚" - and
    this turns that back into the three roles the timeline needs. The onset needs
    backtracking: /kʰ/ in kʰrap is not followed by a vowel, so a left-to-right pass
    that demands one gives up on the cluster. Anything outside the inventory raises
    rather than being silently dropped.
    """
    for onset in _onsets(ipa):
        position = sum(len(symbol) for symbol in onset)
        vowel = _vowel_at(ipa, position)
        if not vowel:
            continue
        position += len(vowel)
        if position == len(ipa):
            return onset, vowel, None
        for symbol in FINAL_PHONEMES:
            if ipa.startswith(symbol, position) and position + len(symbol) == len(ipa):
                return onset, vowel, symbol
    raise LexiconError(
        f"{ipa!r} is not a syllable this inventory can express - "
        "expected [initial][initial]vowel[final]")


def _onsets(ipa):
    """Candidate onsets, two consonants before one, longest symbol first."""
    singles = [symbol for symbol in INITIAL_PHONEMES if ipa.startswith(symbol)]
    for first in singles:
        for second in INITIAL_PHONEMES:
            if ipa.startswith(second, len(first)):
                yield [first, second]
    for first in singles:
        yield [first]
    yield []


def _vowel_at(ipa, position):
    for symbol in VOWEL_PHONEMES:
        if ipa.startswith(symbol, position):
            return symbol
    return None


def load_lexicon(path=None):
    """Surface form -> list of (initials, vowel, final). Missing file means empty."""
    path = Path(path) if path else DEFAULT_LEXICON
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    lexicon = {}
    for word, syllables in data.get("words", {}).items():
        lexicon[strip_tones(word)] = [parse_ipa_syllable(s) for s in syllables]
    return lexicon


_LEXICON_CACHE = {}


def lexicon(path=None):
    key = str(path) if path else "default"
    if key not in _LEXICON_CACHE:
        _LEXICON_CACHE[key] = load_lexicon(path)
    return _LEXICON_CACHE[key]


# Scores for the parse search. Only penalties are scored, never a per-syllable bonus:
# a positive base would make "more syllables" win by arithmetic rather than by fit.
CLUSTER_SPLIT_PENALTY = -8      # taking a coda that is really the head of a cluster
INHERENT_O_PENALTY = -3         # legal (khon, nok) but rarer than a written vowel
INHERENT_A_PENALTY = -6         # bare consonant, no vowel written at all
CLUSTER_ONSET_BONUS = 2         # recognising a real cluster is evidence, not luck
UNPARSED_PENALTY = -50          # never trade a parsed character for an unparsed one


LEXICON_BONUS = 15              # a listed pronunciation outranks any rule reading


def _candidates_at(run, position):
    out = []
    for pattern, vowel, glide, kind in COMPILED:
        match = pattern.match(run, position)
        if match:
            out.append((match, vowel, glide, kind))
    return out


def _lexicon_at(run, position, entries):
    """Longest lexicon entry starting here, as (length, syllables)."""
    for word in sorted(entries, key=len, reverse=True):
        if word and run.startswith(word, position):
            return len(word), entries[word]
    return None


def _score(run, match, kind):
    """How well one syllable fits, judged only by what it costs to believe it."""
    score = 0
    if kind == "inherent_o":
        score += INHERENT_O_PENALTY
    elif kind == "inherent_a":
        score += INHERENT_A_PENALTY

    if match.groupdict().get("f"):
        # The final is always the last character of its pattern. If that character
        # forms a cluster with the next one, it is far more likely to be the onset of
        # the following syllable: /diː.kʰrap/, not /diːk.rap/.
        final_at = match.end() - 1
        pair = run[final_at:final_at + 2]
        if pair in CLUSTERS or (pair[:1] == "\u0e2b" and pair[1:2] in SONORANTS):
            score += CLUSTER_SPLIT_PENALTY

    if len(match.group("i")) == 2 and match.group("i") in CLUSTERS:
        score += CLUSTER_ONSET_BONUS
    return score


def _best_parse(run, entries=None):
    """Highest-scoring segmentation of an unbroken Thai run.

    Greedy longest-match cannot do this. In dii-khrap the coda slot of one syllable
    and the cluster onset of the next compete for the same character, and both
    readings are locally legal; only scoring the whole run separates them. Without a
    pronunciation dictionary this is the honest ceiling - see the module docstring.
    """
    entries = lexicon() if entries is None else entries
    length = len(run)
    best = [None] * (length + 1)
    best[length] = (0, [], [])

    for position in range(length - 1, -1, -1):
        options = []

        listed = _lexicon_at(run, position, entries)
        if listed:
            span, syllables = listed
            score, tail, unparsed = best[position + span]
            options.append((score + LEXICON_BONUS * len(syllables),
                            [("lexicon", run[position:position + span], syllables)] + tail,
                            unparsed))

        for match, vowel, glide, kind in _candidates_at(run, position):
            score, syllables, unparsed = best[match.end()]
            options.append((score + _score(run, match, kind),
                            [(match, vowel, glide)] + syllables,
                            unparsed))
        score, syllables, unparsed = best[position + 1]
        options.append((score + UNPARSED_PENALTY, syllables, [position] + unparsed))
        best[position] = max(options, key=lambda option: option[0])

    return best[0]


def _build_syllables(run, parsed, first_index):
    syllables = []
    for entry in parsed:
        if entry[0] == "lexicon":
            _, surface, listed = entry
            for initials, vowel, final in listed:
                syllables.append(Syllable(surface, list(initials), vowel, final,
                                          first_index + len(syllables)))
            continue
        match, vowel, glide = entry
        initial = _resolve_initial(match.group("i"))
        final = None
        if match.groupdict().get("f"):
            final = FINAL_IPA.get(match.group("f"))
        elif glide:
            final = glide
        syllables.append(Syllable(match.group(0), initial, vowel, final,
                                  first_index + len(syllables)))
    return syllables


def _resolve_initial(raw):
    """Orthographic initial to IPA. Handles clusters, silent HO HIP, silent O ANG."""
    if raw in IRREGULAR_INITIALS:
        return [IRREGULAR_INITIALS[raw]]
    if len(raw) == 2 and raw[0] == "\u0e2b" and raw[1] in SONORANTS:
        return [INITIAL_IPA[raw[1]]]                  # leading HO HIP marks tone only
    if raw == O_LEADING:
        return ["j"]                                   # ya, yuu, yaang, yaak
    if raw in CLUSTERS:
        return [INITIAL_IPA[raw[0]], INITIAL_IPA[raw[1]]]
    return [INITIAL_IPA.get(raw[0], "\u0294")]


def _parse_run(run, first_index=0):
    """Parse an unbroken Thai run into syllables, discarding the unparsed record."""
    _, parsed, _ = _best_parse(run)
    return _build_syllables(run, parsed, first_index)


def phonemize(text, engine=None):
    """Thai text to a G2PResult.

    `engine` selects the backend; None means the built-in parser. External engines
    register through `register_engine` (DECISIONS.md ADR-021).
    """
    if engine and engine != "builtin":
        if engine not in ENGINES:
            raise ValueError(
                f"unknown G2P engine {engine!r} - have {', '.join(available_engines())}")
        return ENGINES[engine](text)
    return _builtin(text)


def _builtin(text):
    source = normalise(text)
    syllables, unparsed, breaks = [], [], []

    position = 0
    while position < len(source):
        ch = source[position]
        if not is_thai(ch):
            if syllables and (ch.isspace() or ch in ".,!?;:\u0e5a\u0e5b"):
                if not breaks or breaks[-1] != len(syllables) - 1:
                    breaks.append(len(syllables) - 1)
            position += 1
            continue

        run_end = position
        while run_end < len(source) and is_thai(source[run_end]):
            run_end += 1
        run = source[position:run_end]

        _, parsed, skipped = _best_parse(run)
        syllables.extend(_build_syllables(run, parsed, len(syllables)))
        unparsed.extend((position + offset, run[offset]) for offset in skipped)
        position = run_end

    return G2PResult(text, syllables, unparsed, breaks)


ENGINES = {}


def register_engine(name, function):
    """Register an external G2P backend, e.g. a pythainlp-backed one."""
    ENGINES[name] = function


def available_engines():
    return ["builtin"] + sorted(ENGINES)
