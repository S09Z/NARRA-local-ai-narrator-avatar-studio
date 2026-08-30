#!/usr/bin/env python3
"""Compile and lint NARRA prompt sources (PHASE 2.2-2.4).

Assembles a generation prompt from the master character prompt plus one asset
prompt file, in the fixed block order from PROMPT_GUIDE.md section 1, and derives
the deterministic seed from PLAN.md section 2.4.

Usage:
    compile_prompt.py visemes/mbp-v1.0.md          compiled prompt text
    compile_prompt.py visemes/mbp-v1.0.md --json   metadata record (ASSET_SPEC 11)
    compile_prompt.py --lint                       lint every file under prompts/

Exit code 0 = success, 1 = compile or lint failure, 2 = usage error.

Format is documented in prompts/README.md. Parsing is stdlib only - no YAML
dependency (DECISIONS.md ADR-007).
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(os.environ.get("NARRA_REPO", Path(__file__).resolve().parents[2]))
PROMPTS = REPO / "prompts"
MASTER_DIR = PROMPTS / "master"

# PROMPT_GUIDE.md section 1 - emission order is fixed regardless of file order,
# so identity constraints always precede task instructions.
BLOCK_ORDER = [
    "CHARACTER", "PRESERVATION", "TASK", "EXPRESSION", "VISEME",
    "POSE", "CAMERA", "LIGHTING", "STYLE", "OUTPUT",
]
BLOCKS = set(BLOCK_ORDER)

KINDS = {"master", "expression", "viseme", "pose", "diagnostic"}

# Canonical sets - ASSET_SPEC.md sections 6, 7, 8. Order defines the seed offset.
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

CANONICAL = {"expression": EXPRESSIONS, "viseme": VISEMES, "pose": POSES}

# PLAN.md section 2.4, DECISIONS.md ADR-009
SEED_BASE = {"diagnostic": 1000, "expression": 10000, "viseme": 20000, "pose": 30000}
SEED_SPAN = 1000

# PROMPT_GUIDE.md section 3. The preserved features are listed explicitly rather
# than pasted as fixed text, because the fixed text contradicts itself the moment
# the TASK touches one of the features it names: an expression edit would emit
# "identical eyebrows ... do not change anything except the eyebrows". The features
# a TASK touches are removed from the list by the 'touches' header.
PRESERVABLE = {
    "face": "face shape",
    "eyes": "eye shape and position",
    "eyebrows": "eyebrows",
    "nose": "nose",
    "mouth": "mouth shape and position",
    "hair": "hairstyle and hair color",
    "skin": "skin tone",
    "clothing": "clothing",
    "accessories": "accessories",
    "style": "art style",
    "lighting": "lighting",
    "camera": "camera framing",
}
PRESERVE_ORDER = list(PRESERVABLE)

# What each asset class is allowed to touch (character-bible.md section 14).
# Diagnostics declare their own, since proving containment is their whole purpose.
DEFAULT_TOUCHES = {
    "expression": ["eyes", "eyebrows", "mouth"],
    "viseme": ["mouth"],
    "pose": ["camera"],
}

PRESERVATION_TEMPLATE = (
    "Keep the same person: identical {preserved} as the reference image.\n"
    "Do not change anything except {task_target}."
)

# PROMPT_GUIDE.md section 8 - targeted correction, applied by group, never wholesale.
# Each term is tagged with the feature it guards so that a TASK which legitimately
# changes that feature does not also carry a negative forbidding it. Without this,
# a "change only the hair" prompt emits "different hairstyle" as a negative and
# fights itself. A term tagged None is never dropped - "moved mouth position" still
# applies to a viseme, whose mouth shape changes but whose mouth position must not.
NEGATIVE_GROUPS = {
    "identity": [
        ("different person", None),
        ("different face shape", "face"),
        ("different hairstyle", "hair"),
        ("different hair color", "hair"),
        ("different clothing", "clothing"),
        ("aged face", "face"),
    ],
    "framing": [
        ("changed camera distance", "camera"),
        ("changed head size", "camera"),
        ("cropped head", "camera"),
        ("tilted head", "camera"),
    ],
    "viseme": [
        ("changed eyes", "eyes"),
        ("changed eyebrows", "eyebrows"),
        ("changed expression", "eyes"),
        ("moved mouth position", None),
    ],
    "render": [
        ("photorealistic drift", None),
        ("style change", "style"),
        ("added text", None),
        ("watermark", None),
        ("extra limbs", None),
    ],
}
NEGATIVES_BY_KIND = {
    # pose omits "framing": a pose changes camera class by design, so those terms
    # would fight its own positive prompt.
    "expression": ["identity", "framing", "render"],
    "viseme": ["identity", "framing", "viseme", "render"],
    "pose": ["identity", "render"],
    "diagnostic": ["identity", "framing", "render"],
}

# PROMPT_GUIDE.md section 1 - carry no visual meaning for FLUX, dilute every other term.
FILLER_TERMS = [
    "beautiful", "high quality", "best quality", "masterpiece", "award winning",
    "ultra detailed", "highly detailed", "intricate details", "8k", "4k",
]
# Prompts describe the result, not the editing operation. Kept to unambiguous
# pipeline vocabulary - "mask" and "layer" have legitimate visual meanings.
EDIT_OP_TERMS = ["inpaint", "img2img", "denoise", "latent", "cfg scale", "apply a mask"]

FILENAME_RE = re.compile(r"^(?P<id>.+)-v(?P<version>\d+\.\d+)$")
HEADING_RE = re.compile(r"^##\s+([A-Z]+)\s*$")
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


class PromptError(Exception):
    """A prompt file is malformed or violates a PROMPT_GUIDE rule."""


class PromptFile:
    def __init__(self, path, header, blocks):
        self.path = path
        self.header = header
        self.blocks = blocks

    @property
    def kind(self):
        return self.header.get("kind", "")

    @property
    def version(self):
        return self.header.get("version", "")

    @property
    def id(self):
        return self.header.get("id", "")

    @property
    def label(self):
        try:
            return str(self.path.relative_to(REPO))
        except ValueError:
            return str(self.path)

    def prompt_version(self):
        return f"{self.id}-v{self.version}"


def parse(path):
    """Parse a prompt file into (header dict, ordered block dict)."""
    text = path.read_text(encoding="utf-8")
    text = COMMENT_RE.sub("", text)
    lines = text.splitlines()

    header = {}
    if lines and lines[0].strip() == "---":
        try:
            end = lines.index("---", 1)
        except ValueError:
            raise PromptError(f"{path.name}: header opened with --- but never closed")
        for raw in lines[1:end]:
            if not raw.strip():
                continue
            if ":" not in raw:
                raise PromptError(f"{path.name}: header line is not 'key: value': {raw!r}")
            key, value = raw.split(":", 1)
            header[key.strip()] = value.strip()
        lines = lines[end + 1:]
    else:
        raise PromptError(f"{path.name}: missing the --- header block (prompts/README.md 2)")

    blocks = {}
    current = None
    buffer = []
    for raw in lines:
        match = HEADING_RE.match(raw)
        if match:
            if current:
                blocks[current] = "\n".join(buffer).strip()
            current = match.group(1)
            if current in blocks:
                raise PromptError(f"{path.name}: block {current} appears twice")
            buffer = []
        elif current:
            buffer.append(raw)
    if current:
        blocks[current] = "\n".join(buffer).strip()

    return PromptFile(path, header, blocks)


def canonical_index(kind, asset_name):
    """Position of asset_name in its canonical set, or None if it is not a member."""
    entries = CANONICAL.get(kind)
    if entries is None:
        return None
    lowered = [entry.lower() for entry in entries]
    try:
        return lowered.index(asset_name.lower())
    except ValueError:
        return None


def canonical_name(kind, asset_name):
    """The canonically cased name - visemes are uppercase in metadata (ASSET_SPEC 5)."""
    index = canonical_index(kind, asset_name)
    return CANONICAL[kind][index] if index is not None else asset_name


def derive_seed(prompt):
    """seed = range base + index in the canonical set (prompts/README.md 4)."""
    kind = prompt.kind
    if kind == "diagnostic":
        raw = prompt.header.get("seed")
        if raw is None:
            raise PromptError(f"{prompt.label}: diagnostic prompts need an explicit 'seed'")
        try:
            seed = int(raw)
        except ValueError:
            raise PromptError(f"{prompt.label}: seed {raw!r} is not an integer")
        base = SEED_BASE["diagnostic"]
        if not base <= seed < base + SEED_SPAN:
            raise PromptError(
                f"{prompt.label}: seed {seed} is outside the diagnostic range "
                f"{base}-{base + SEED_SPAN - 1} (DECISIONS.md ADR-009)")
        return seed

    index = canonical_index(kind, prompt.header.get("asset_name", ""))
    if index is None:
        raise PromptError(
            f"{prompt.label}: asset_name {prompt.header.get('asset_name')!r} is not in the "
            f"canonical {kind} set - {', '.join(CANONICAL[kind])}")
    return SEED_BASE[kind] + index


def find_master():
    candidates = sorted(MASTER_DIR.glob("master-character-v*.md"))
    if not candidates:
        raise PromptError(
            f"no master prompt found in {MASTER_DIR.relative_to(REPO)} "
            "(PLAN.md 2.1)")
    return candidates[-1]


def touched_features(prompt):
    """Features the TASK is allowed to change - removed from the preserved list."""
    raw = prompt.header.get("touches")
    if raw is None:
        if prompt.kind not in DEFAULT_TOUCHES:
            raise PromptError(
                f"{prompt.label}: 'touches' is required for {prompt.kind} prompts - it "
                "names which features leave the PRESERVATION list")
        return list(DEFAULT_TOUCHES[prompt.kind])

    features = [item.strip() for item in raw.split(",") if item.strip()]
    unknown = [item for item in features if item not in PRESERVABLE]
    if unknown:
        raise PromptError(
            f"{prompt.label}: unknown touches {', '.join(unknown)} - one of "
            f"{', '.join(PRESERVE_ORDER)}")
    return features


def build_preservation(prompt):
    if prompt.header.get("preservation", "auto") == "manual":
        block = prompt.blocks.get("PRESERVATION")
        if not block:
            raise PromptError(
                f"{prompt.label}: preservation is 'manual' but no PRESERVATION block exists")
        return block

    if "PRESERVATION" in prompt.blocks:
        raise PromptError(
            f"{prompt.label}: PRESERVATION block present but header does not say "
            "'preservation: manual' - the block would be silently replaced")

    target = prompt.header.get("task_target")
    if not target:
        raise PromptError(
            f"{prompt.label}: 'task_target' is required - it names the one region the "
            "TASK may change and fills the PRESERVATION template (PROMPT_GUIDE.md 3)")

    touched = set(touched_features(prompt))
    kept = [PRESERVABLE[key] for key in PRESERVE_ORDER if key not in touched]
    if not kept:
        raise PromptError(f"{prompt.label}: 'touches' leaves nothing preserved")
    preserved = ", ".join(kept[:-1]) + f", and {kept[-1]}" if len(kept) > 1 else kept[0]
    return PRESERVATION_TEMPLATE.format(preserved=preserved, task_target=target)


def negatives_for(kind, touched=()):
    """Negative groups for an asset class, minus terms the TASK legitimately changes."""
    touched = set(touched)
    lines = []
    for group in NEGATIVES_BY_KIND[kind]:
        terms = [term for term, feature in NEGATIVE_GROUPS[group]
                 if feature is None or feature not in touched]
        if terms:
            lines.append(", ".join(terms))
    return ",\n".join(lines)


def compile_prompt(asset_path, master_path=None):
    asset = parse(asset_path)
    lint_file(asset, strict=True)

    if asset.kind == "master":
        raise PromptError(
            f"{asset.label}: the master prompt is descriptive only and is not compiled "
            "on its own (PROMPT_GUIDE.md 2)")

    master_path = master_path or find_master()
    master = parse(master_path)
    lint_file(master, strict=True)

    merged = dict(master.blocks)
    merged.update(asset.blocks)          # asset wins - a pose overrides master CAMERA
    merged["PRESERVATION"] = build_preservation(asset)

    parts = []
    for name in BLOCK_ORDER:
        body = merged.get(name, "").strip()
        if not body:
            continue                      # a block that does not apply is omitted
        indented = "\n".join("  " + line if line.strip() else "" for line in body.splitlines())
        parts.append(f"{name}:\n{indented}")

    compiled = "\n\n".join(parts)
    negative = negatives_for(asset.kind, touched_features(asset))

    return {
        "asset_type": asset.kind,
        "asset_name": canonical_name(asset.kind, asset.header.get("asset_name", "")),
        "seed": derive_seed(asset),
        "master_version": master.prompt_version(),
        "asset_prompt_version": asset.prompt_version(),
        "master_file": master.label,
        "asset_file": asset.label,
        "camera_class": asset.header.get("camera_class"),
        "compiled": compiled,
        "negative": negative,
    }


def lint_file(prompt, strict=False):
    """Return a list of rule violations. strict=True raises on the first one."""
    problems = []

    def fail(message):
        problems.append(f"{prompt.label}: {message}")

    stem_match = FILENAME_RE.match(prompt.path.stem)
    if not stem_match:
        fail("filename must be '<id>-v<MAJOR>.<MINOR>.md' (PROMPT_GUIDE.md 1)")
    else:
        if prompt.id != stem_match.group("id"):
            fail(f"header id {prompt.id!r} does not match filename "
                 f"{stem_match.group('id')!r}")
        if prompt.version != stem_match.group("version"):
            fail(f"header version {prompt.version!r} does not match filename "
                 f"v{stem_match.group('version')}")

    if prompt.kind not in KINDS:
        fail(f"unknown kind {prompt.kind!r} - one of {', '.join(sorted(KINDS))}")

    for name, body in prompt.blocks.items():
        if name not in BLOCKS:
            fail(f"unknown block {name!r} - a typo here silently drops it from every "
                 f"generation. Valid: {', '.join(BLOCK_ORDER)}")
        if not body.strip():
            fail(f"block {name} is empty - omit it instead (PROMPT_GUIDE.md 1)")

    if prompt.kind == "master":
        if "TASK" in prompt.blocks:
            fail("the master prompt never contains a TASK (PROMPT_GUIDE.md 2)")
    else:
        task_count = 1 if "TASK" in prompt.blocks else 0
        if task_count != 1:
            fail("exactly one TASK block is required - two changes are two generations "
                 "(PROMPT_GUIDE.md 1)")
        if not prompt.header.get("asset_name"):
            fail("'asset_name' is required")
        elif prompt.kind in CANONICAL and canonical_index(
                prompt.kind, prompt.header["asset_name"]) is None:
            fail(f"asset_name {prompt.header['asset_name']!r} is not in the canonical "
                 f"{prompt.kind} set (ASSET_SPEC.md)")

    if prompt.kind not in ("master",):
        try:
            touched_features(prompt)
        except PromptError as exc:
            problems.append(str(exc))

    if prompt.kind == "expression" and "VISEME" in prompt.blocks:
        fail("expression prompts must not specify a viseme - expression assets carry a "
             "REST mouth so the viseme layer can composite over them (PROMPT_GUIDE.md 5)")
    if prompt.kind == "viseme" and "EXPRESSION" in prompt.blocks:
        fail("viseme prompts must not contain an EXPRESSION block - expression, gaze, and "
             "eyebrows are held identical to REST (PROMPT_GUIDE.md 6)")
    if prompt.kind == "pose":
        camera_class = prompt.header.get("camera_class")
        if camera_class not in CAMERA_CLASSES:
            fail(f"pose prompts need a valid 'camera_class' - one of "
                 f"{', '.join(sorted(CAMERA_CLASSES))} (ASSET_SPEC.md 8)")

    haystack = " ".join(prompt.blocks.values()).lower()
    for term in FILLER_TERMS:
        if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", haystack):
            fail(f"filler term {term!r} carries no visual meaning for FLUX and dilutes "
                 "every other term (PROMPT_GUIDE.md 1)")
    for term in EDIT_OP_TERMS:
        if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", haystack):
            fail(f"editing-operation term {term!r} - describe the result, not the "
                 "operation (PROMPT_GUIDE.md 1)")

    if strict and problems:
        raise PromptError(problems[0])
    return problems


def lint_all():
    files = sorted(
        path for path in PROMPTS.rglob("*.md")
        if path.name != "README.md"
    )
    if not files:
        print(f"no prompt files found under {PROMPTS.relative_to(REPO)}")
        return 0

    problems = []
    for path in files:
        try:
            prompt = parse(path)
        except PromptError as exc:
            problems.append(str(exc))
            continue
        problems.extend(lint_file(prompt))
        if prompt.kind != "master":
            try:
                derive_seed(prompt)
            except PromptError as exc:
                problems.append(str(exc))

    for path in files:
        print(f"  checked {path.relative_to(REPO)}")

    if problems:
        print(f"\n{len(problems)} problem(s):")
        for problem in problems:
            print(f"  [FAIL] {problem}")
        return 1

    print(f"\n{len(files)} prompt file(s) OK.")
    return 0


def resolve(candidate):
    """Accept a path relative to prompts/, to the repo, or absolute."""
    for base in (PROMPTS, REPO, Path.cwd()):
        path = base / candidate
        if path.is_file():
            return path
    path = Path(candidate)
    return path if path.is_file() else None


def main():
    parser = argparse.ArgumentParser(
        description="Compile and lint NARRA prompt sources (PHASE 2.2-2.4).")
    parser.add_argument("prompt", nargs="?", help="asset prompt file, e.g. visemes/mbp-v1.0.md")
    parser.add_argument("--json", action="store_true",
                        help="emit the metadata record instead of prompt text")
    parser.add_argument("--lint", action="store_true", help="lint every file under prompts/")
    parser.add_argument("--master", help="override the master prompt file")
    args = parser.parse_args()

    if args.lint:
        if args.prompt:
            parser.error("--lint checks every prompt file; do not also name one")
        return lint_all()

    if not args.prompt:
        parser.error("name a prompt file, or use --lint")

    path = resolve(args.prompt)
    if path is None:
        print(f"error: prompt file not found: {args.prompt}", file=sys.stderr)
        return 2

    master_path = resolve(args.master) if args.master else None
    if args.master and master_path is None:
        print(f"error: master prompt not found: {args.master}", file=sys.stderr)
        return 2

    try:
        result = compile_prompt(path, master_path)
    except PromptError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result["compiled"])
        print(f"\nNEGATIVE:\n{result['negative']}")
        print(f"\nseed: {result['seed']}")
        print(f"prompt versions: {result['master_version']} + {result['asset_prompt_version']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
