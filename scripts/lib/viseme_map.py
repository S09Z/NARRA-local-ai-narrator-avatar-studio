"""Phoneme to viseme - the PHASE 4.2 table, in a form code can read (PHASE 7.3).

docs/thai-viseme/thai-viseme-mapping.md is the prose and the reasoning. This module
reads docs/thai-viseme/thai-viseme-map.json, which is the same table as data. They are
checked against each other by tests/audio/test_viseme_map.py, because a mapping that
drifts from its own documentation is worse than either one alone (DECISIONS.md ADR-019).

Two phonemes map to nothing: /h/ and /ʔ/ have no visible articulation, so mapping.md
section 1 says to hold the surrounding vowel. `viseme_for` returns an empty list for
them, and the timeline builder gives their time to the neighbouring vowel.

Not a package (DECISIONS.md ADR-007, ADR-011). Importers do:

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
    import viseme_map
"""

import json
from pathlib import Path

DEFAULT_MAP = (Path(__file__).resolve().parents[2]
               / "docs" / "thai-viseme" / "thai-viseme-map.json")

_CACHE = {}


class VisemeMapError(Exception):
    """The mapping file is missing, malformed, or names a viseme outside the set."""


def load(path=None):
    """Load and validate the mapping. Cached per path."""
    key = str(path) if path else "default"
    if key not in _CACHE:
        _CACHE[key] = _load(Path(path) if path else DEFAULT_MAP)
    return _CACHE[key]


def _load(path):
    if not path.exists():
        raise VisemeMapError(f"mapping not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))

    allowed = set(data.get("viseme_set") or [])
    if not allowed:
        raise VisemeMapError(f"{path} declares no viseme_set")

    for section in ("initial", "final", "vowel", "loanword"):
        for phoneme, viseme in (data.get(section) or {}).items():
            if viseme is not None and viseme not in allowed:
                raise VisemeMapError(
                    f"{section}/{phoneme} maps to {viseme!r}, which is not in the "
                    f"viseme set")
    for phoneme, visemes in (data.get("diphthong") or {}).items():
        for viseme in visemes:
            if viseme not in allowed:
                raise VisemeMapError(
                    f"diphthong/{phoneme} maps to {viseme!r}, which is not in the "
                    f"viseme set")
    if data.get("silence") not in allowed:
        raise VisemeMapError(f"{path} silence viseme {data.get('silence')!r} is not "
                             "in the viseme set")
    return data


def viseme_for(phoneme, role="vowel", mapping=None):
    """Visemes for one phoneme in one role. Empty list means no visible articulation.

    Role matters: /m/ as an initial and /m/ as a final are the same shape here, but
    /w/ and /j/ are onsets in one role and offglides in the other, and mapping.md
    lists them separately so the two can diverge without touching code.
    """
    data = mapping or load()

    if role == "vowel":
        if phoneme in data["diphthong"]:
            return list(data["diphthong"][phoneme])
        viseme = data["vowel"].get(phoneme)
    elif role == "final":
        viseme = data["final"].get(phoneme)
    else:
        viseme = data["initial"].get(phoneme)
        if viseme is None and phoneme not in data["initial"]:
            viseme = data["loanword"].get(phoneme)

    if viseme is None:
        return []
    return [viseme]


def silence(mapping=None):
    return (mapping or load())["silence"]


def viseme_set(mapping=None):
    return list((mapping or load())["viseme_set"])


def unmapped_phonemes(phonemes, mapping=None):
    """Phonemes with no entry at all - distinct from those that map to nothing."""
    data = mapping or load()
    known = (set(data["initial"]) | set(data["final"]) | set(data["vowel"])
             | set(data["diphthong"]) | set(data["loanword"]))
    return sorted({phoneme for phoneme in phonemes if phoneme not in known})
