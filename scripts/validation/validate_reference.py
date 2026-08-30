#!/usr/bin/env python3
"""Validate and import the NARRA canonical reference image (PHASE 1.1).

The reference is the source of truth for every derived asset, so it is checked
against ASSET_SPEC.md before it is allowed into character/reference/.

Usage:
    validate_reference.py <candidate.png>            validate only, write nothing
    validate_reference.py <candidate.png> --import   validate, then import on pass
    validate_reference.py --check-imported           re-validate what is already imported

Exit code 0 = all checks passed, 1 = at least one FAIL, 2 = usage error.

Pillow is used for pixel-level checks. Without it the script still runs and
performs header-level checks from the stdlib, and reports the pixel checks as
skipped rather than passed.
"""

import argparse
import hashlib
import json
import os
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

# NARRA_REPO lets the test suite point the importer at a throwaway tree.
REPO = Path(os.environ.get("NARRA_REPO", Path(__file__).resolve().parents[2]))

CHARACTER = "narra"
VERSION = 1
REF_DIR = REPO / "character" / "reference"
MASTER = REF_DIR / f"{CHARACTER}-reference-master-v{VERSION}.png"
ALIAS = REF_DIR / "master.png"
SIDECAR = REF_DIR / f"{CHARACTER}-reference-master-v{VERSION}.json"
MIRROR = REPO / "metadata" / "generations" / f"{CHARACTER}-reference-master-v{VERSION}.json"

# ASSET_SPEC.md sections 1-4
REQUIRED_SIZE = (1024, 1024)
REQUIRED_MODE = "RGBA"
REQUIRED_BIT_DEPTH = 8
MAX_SEMI_TRANSPARENT_FRACTION = 0.06   # antialiased silhouette edge only
MIN_OPAQUE_FRACTION = 0.10             # a character occupies a real part of the frame
MAX_OPAQUE_FRACTION = 0.95             # ...but is not a full-bleed background

PASS, FAIL, WARN, SKIP = "PASS", "FAIL", "WARN", "SKIP"

PNG_COLOR_TYPES = {0: "L", 2: "RGB", 3: "P", 4: "LA", 6: "RGBA"}


class Report:
    """Accumulates check results and decides the outcome."""

    def __init__(self):
        self.rows = []

    def add(self, level, name, detail=""):
        self.rows.append((level, name, detail))

    def failed(self):
        return any(level == FAIL for level, _, _ in self.rows)

    def render(self):
        width = max(len(name) for _, name, _ in self.rows)
        lines = []
        for level, name, detail in self.rows:
            line = f"  [{level}] {name.ljust(width)}"
            if detail:
                line += f"  {detail}"
            lines.append(line)
        return "\n".join(lines)


def read_png_header(path):
    """Return (width, height, bit_depth, mode) from the IHDR chunk, stdlib only."""
    with path.open("rb") as fh:
        if fh.read(8) != b"\x89PNG\r\n\x1a\n":
            return None
        length, chunk = struct.unpack(">I4s", fh.read(8))
        if chunk != b"IHDR" or length != 13:
            return None
        width, height, bit_depth, color_type = struct.unpack(">IIBB", fh.read(10))
    return width, height, bit_depth, PNG_COLOR_TYPES.get(color_type, f"?{color_type}")


def load_pillow():
    try:
        from PIL import Image
        return Image
    except ImportError:
        return None


def check_header(path, report):
    header = read_png_header(path)
    if header is None:
        report.add(FAIL, "format/png", "not a PNG file (ASSET_SPEC 3)")
        return None

    width, height, bit_depth, mode = header
    report.add(PASS, "format/png", "PNG signature and IHDR present")

    if (width, height) == REQUIRED_SIZE:
        report.add(PASS, "resolution", f"{width}x{height}")
    else:
        report.add(FAIL, "resolution",
                   f"{width}x{height}, required {REQUIRED_SIZE[0]}x{REQUIRED_SIZE[1]} (ASSET_SPEC 1)")

    if width == height:
        report.add(PASS, "aspect-ratio", "1:1")
    else:
        report.add(FAIL, "aspect-ratio", f"{width}:{height}, required 1:1 (ASSET_SPEC 2)")

    if bit_depth == REQUIRED_BIT_DEPTH:
        report.add(PASS, "bit-depth", "8 bits per channel")
    else:
        report.add(FAIL, "bit-depth", f"{bit_depth}, required 8 (ASSET_SPEC 3)")

    if mode == REQUIRED_MODE:
        report.add(PASS, "color-mode", "RGBA")
    else:
        report.add(FAIL, "color-mode", f"{mode}, required RGBA (ASSET_SPEC 4)")

    return header


def check_pixels(path, report):
    Image = load_pillow()
    if Image is None:
        for name in ("alpha/background", "alpha/edge", "alpha/coverage", "color-space"):
            report.add(SKIP, name, "Pillow not installed - run: pip install Pillow")
        return

    with Image.open(path) as img:
        if img.info.get("icc_profile"):
            report.add(WARN, "color-space",
                       "embedded ICC profile found - strip it, the pipeline assumes sRGB (ASSET_SPEC 3)")
        else:
            report.add(PASS, "color-space", "no embedded ICC profile, assumed sRGB")

        if img.mode != "RGBA":
            report.add(SKIP, "alpha/background", "image is not RGBA")
            report.add(SKIP, "alpha/edge", "image is not RGBA")
            report.add(SKIP, "alpha/coverage", "image is not RGBA")
            return

        alpha = img.getchannel("A")
        width, height = img.size
        corners = [
            alpha.getpixel((0, 0)),
            alpha.getpixel((width - 1, 0)),
            alpha.getpixel((0, height - 1)),
            alpha.getpixel((width - 1, height - 1)),
        ]
        if all(value == 0 for value in corners):
            report.add(PASS, "alpha/background", "all four corners fully transparent")
        else:
            report.add(FAIL, "alpha/background",
                       f"corner alpha {corners}, expected [0, 0, 0, 0] - background is not "
                       "transparent (ASSET_SPEC 4)")

        histogram = alpha.histogram()
        total = float(width * height)
        transparent = histogram[0]
        opaque = histogram[255]
        semi = total - transparent - opaque

        semi_fraction = semi / total
        if semi_fraction <= MAX_SEMI_TRANSPARENT_FRACTION:
            report.add(PASS, "alpha/edge", f"{semi_fraction:.2%} semi-transparent")
        else:
            report.add(FAIL, "alpha/edge",
                       f"{semi_fraction:.2%} semi-transparent, max "
                       f"{MAX_SEMI_TRANSPARENT_FRACTION:.0%} - soft matte or halo "
                       "from the generation background (ASSET_SPEC 4)")

        opaque_fraction = opaque / total
        if MIN_OPAQUE_FRACTION <= opaque_fraction <= MAX_OPAQUE_FRACTION:
            report.add(PASS, "alpha/coverage", f"{opaque_fraction:.1%} of frame opaque")
        else:
            report.add(FAIL, "alpha/coverage",
                       f"{opaque_fraction:.1%} of frame opaque, expected "
                       f"{MIN_OPAQUE_FRACTION:.0%}-{MAX_OPAQUE_FRACTION:.0%} - "
                       "cutout is empty or the background was not removed")


def visual_checklist():
    """Checks a script cannot make. Printed so they are not silently skipped."""
    return [
        "REST mouth - relaxed and closed; all 16 visemes are edits of this mouth",
        "Neutral expression, gaze at camera",
        "Head fully in frame; no crop of hair or chin",
        "Head angle is the one angle the whole library will use",
        "Clean alpha edge - no fringe from the generation background",
        "Art style matches the intended library style (character-bible.md section 9)",
    ]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def build_sidecar(path):
    """Reference metadata per ASSET_SPEC.md section 11.

    Generation fields are null: this file is imported, not generated by this
    pipeline. They are filled in if and when the reference is regenerated
    locally, at which point the reference becomes reproducible from metadata alone.
    """
    return {
        "character": CHARACTER,
        "asset_type": "reference",
        "asset_name": "master",
        "version": VERSION,
        "file": str(MASTER.relative_to(REPO)),
        "reference": None,
        "sha256": sha256(path),
        "model": {"name": None, "precision": None, "file": None},
        "workflow": {"file": None, "version": None},
        "prompt": {
            "master_version": None,
            "asset_prompt_version": None,
            "compiled": None,
            "negative": None,
        },
        "generation": {
            "seed": None,
            "steps": None,
            "cfg": None,
            "sampler": None,
            "scheduler": None,
            "denoise": None,
            "resolution": list(REQUIRED_SIZE),
        },
        "mouth_anchor": {
            "anchor_x": None,
            "anchor_y": None,
            "mouth_width": None,
            "mouth_height": None,
        },
        "environment": {"comfyui_version": "", "custom_nodes": []},
        "validation": {
            "status": "imported",
            "validated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "notes": "Automated checks in scripts/validation/validate_reference.py passed. "
                     "Visual checklist and PHASE 1.4 baseline tests still required before "
                     "status becomes approved.",
        },
        "generated_at": None,
    }


def do_import(path):
    REF_DIR.mkdir(parents=True, exist_ok=True)
    MIRROR.parent.mkdir(parents=True, exist_ok=True)

    data = path.read_bytes()
    MASTER.write_bytes(data)
    ALIAS.write_bytes(data)

    sidecar = json.dumps(build_sidecar(MASTER), indent=2) + "\n"
    SIDECAR.write_text(sidecar)
    MIRROR.write_text(sidecar)

    print("\nImported:")
    for target in (MASTER, ALIAS, SIDECAR, MIRROR):
        print(f"  {target.relative_to(REPO)}")


def check_imported(report):
    if not MASTER.exists():
        report.add(FAIL, "imported/master", f"{MASTER.relative_to(REPO)} not found - run --import")
        return False
    report.add(PASS, "imported/master", str(MASTER.relative_to(REPO)))

    if not ALIAS.exists():
        report.add(FAIL, "imported/alias", "master.png missing (see character/reference/README.md)")
    elif ALIAS.read_bytes() != MASTER.read_bytes():
        report.add(FAIL, "imported/alias",
                   "master.png is not byte-identical to the versioned master - "
                   "workflows and QC would disagree about what the reference is")
    else:
        report.add(PASS, "imported/alias", "master.png byte-identical to versioned master")

    for label, target in (("sidecar", SIDECAR), ("sidecar/mirror", MIRROR)):
        if not target.exists():
            report.add(FAIL, f"imported/{label}", f"{target.relative_to(REPO)} missing (ASSET_SPEC 11)")
            continue
        try:
            recorded = json.loads(target.read_text())
        except json.JSONDecodeError as exc:
            report.add(FAIL, f"imported/{label}", f"invalid JSON: {exc}")
            continue
        if recorded.get("sha256") != sha256(MASTER):
            report.add(FAIL, f"imported/{label}",
                       "sha256 does not match the master image - the reference changed "
                       "without being re-imported")
        else:
            report.add(PASS, f"imported/{label}", "present, sha256 matches")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Validate and import the NARRA canonical reference image (PHASE 1.1).")
    parser.add_argument("candidate", nargs="?", type=Path,
                        help="candidate reference image to validate")
    parser.add_argument("--import", dest="do_import", action="store_true",
                        help="import the candidate if every check passes")
    parser.add_argument("--check-imported", action="store_true",
                        help="re-validate the already-imported reference")
    args = parser.parse_args()

    if not args.candidate and not args.check_imported:
        parser.error("give a candidate image, or --check-imported")
    if args.do_import and args.check_imported:
        parser.error("--import and --check-imported are separate operations")

    report = Report()
    target = args.candidate

    if args.check_imported:
        print(f"Checking imported reference in {REF_DIR.relative_to(REPO)}\n")
        if check_imported(report):
            target = MASTER
    else:
        if not target.exists():
            print(f"error: {target} not found", file=sys.stderr)
            return 2
        print(f"Validating {target}\n")

    if target and target.exists():
        if check_header(target, report):
            check_pixels(target, report)

    print(report.render())

    if report.failed():
        if args.check_imported:
            print("\nFAILED - the imported reference does not match ASSET_SPEC or its "
                  "recorded metadata.")
        else:
            print("\nFAILED - the candidate does not meet ASSET_SPEC. Not imported.")
        return 1

    print("\nAutomated checks passed.")
    print("\nStill to confirm by eye - a script cannot check these:")
    for item in visual_checklist():
        print(f"  [ ] {item}")

    if args.do_import:
        do_import(target)
        print("\nNext: fill character/bible/character-bible.md and visual-spec.md from this image.")
    elif not args.check_imported:
        print("\nRe-run with --import to write it into character/reference/.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
