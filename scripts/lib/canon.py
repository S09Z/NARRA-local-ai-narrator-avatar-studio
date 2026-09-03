"""Canonical asset sets, seed derivation, and naming - the shared source of truth.

Imported by scripts/generation/compile_prompt.py and scripts/validation/validate_asset.py.
Kept in one place because a compiler and a validator that disagree about the viseme set
would silently approve an asset the compiler could never have produced.

Not a package (DECISIONS.md ADR-007, ADR-011). Importers do:

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
    import canon
"""

import re

# ASSET_SPEC.md sections 6, 7, 8. Order defines the seed offset - do not reorder.
EXPRESSIONS = [
    "neutral", "friendly", "happy", "excited", "serious", "concerned",
    "surprised", "confused", "thinking", "explaining", "proud", "embarrassed",
]
VISEMES = [
    "REST", "A", "I", "U", "E", "O", "AE", "AO",
    "MBP", "FV", "TH", "KG", "S", "SH", "L", "N",
]
POSES = [
    "neutral", "explaining", "pointing-left", "pointing-right", "presenting",
    "surprised", "thinking", "concerned", "confident", "excited",
]
CAMERA_CLASSES = {"close-up", "medium", "upper-body", "three-quarter"}

# ASSET_SPEC.md section 6: the only expressions defined by an open mouth. The other
# nine carry a REST mouth so the viseme layer can composite over them (ADR-004).
# An open-mouth expression cannot host a viseme track - the mouth is already spent.
OPEN_MOUTH_EXPRESSIONS = {"excited", "surprised", "explaining"}

# PLAN.md section 5.3
NARRATOR_STATES = ["talking", "explaining", "presenting", "reaction", "emphasis"]
MOUTH_MODES = {"viseme-track", "static"}

CANONICAL = {"expression": EXPRESSIONS, "viseme": VISEMES, "pose": POSES}

# PLAN.md section 6.1: the counts the PHASE 6 gate requires. Held separately from
# the lists above so that quietly dropping a viseme cannot quietly move the gate.
REQUIRED_COUNTS = {"expression": 12, "viseme": 16, "pose": 10}

# PLAN.md section 2.4, DECISIONS.md ADR-009
SEED_BASE = {"diagnostic": 1000, "expression": 10000, "viseme": 20000, "pose": 30000}
SEED_SPAN = 1000

CHARACTER = "narra"

# ASSET_SPEC.md section 5: <character>-<type>-<name>-v<version>.png
FILENAME_RE = re.compile(
    r"^(?P<character>[a-z0-9]+)-(?P<asset_type>[a-z]+)-(?P<name>[a-z0-9-]+)"
    r"-v(?P<version>\d+)$")


class CanonError(Exception):
    """An asset name, type, or seed is outside the canonical definition."""


def index_of(asset_type, asset_name):
    """Position in the canonical set, or None if not a member. Case-insensitive."""
    entries = CANONICAL.get(asset_type)
    if entries is None:
        return None
    lowered = [entry.lower() for entry in entries]
    try:
        return lowered.index(asset_name.lower())
    except ValueError:
        return None


def canonical_name(asset_type, asset_name):
    """Canonically cased name - visemes are uppercase in metadata (ASSET_SPEC 5)."""
    index = index_of(asset_type, asset_name)
    return CANONICAL[asset_type][index] if index is not None else asset_name


def derive_seed(asset_type, asset_name):
    """seed = range base + index in the canonical set (prompts/README.md 4)."""
    index = index_of(asset_type, asset_name)
    if index is None:
        raise CanonError(
            f"{asset_name!r} is not in the canonical {asset_type} set - "
            f"{', '.join(CANONICAL.get(asset_type, []))}")
    return SEED_BASE[asset_type] + index


def seed_in_range(asset_type, seed):
    base = SEED_BASE.get(asset_type)
    return base is not None and base <= seed < base + SEED_SPAN


def parse_filename(stem):
    """Split an asset filename stem per ASSET_SPEC 5, or return None."""
    match = FILENAME_RE.match(stem)
    return match.groupdict() if match else None


def asset_filename(asset_type, asset_name, version=1, character=CHARACTER):
    """Filenames are lowercase kebab-case; visemes lowercase here, uppercase in metadata."""
    return f"{character}-{asset_type}-{asset_name.lower()}-v{version}.png"
