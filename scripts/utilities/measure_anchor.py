#!/usr/bin/env python3
"""Record the mouth anchor and the permitted edit region (PHASE 4.3).

The mouth anchor is the contract that lets any viseme composite onto any
expression or pose (DECISIONS.md ADR-004). It is measured once, by hand, from the
approved reference at REST, and every later asset is held to it.

There is no automatic landmark detector in this project and one is not justified
for a single image (character/bible/visual-spec.md section 9). This tool does the
arithmetic, validates the numbers, and writes them where the validator reads them -
it does not find the mouth for you.

Usage:
    measure_anchor.py --box LEFT TOP RIGHT BOTTOM      pixel coords of the REST mouth
    measure_anchor.py --box ... --edit-region L T R B  set the mask region explicitly
    measure_anchor.py --show                           print the current anchor
    measure_anchor.py --from-diff REF ASSET            measurement aid: what moved?

Exit code 0 = written or shown, 1 = invalid measurement, 2 = usage error.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import canon                                     # noqa: E402
import imagecheck                                # noqa: E402

REPO = Path(os.environ.get("NARRA_REPO", Path(__file__).resolve().parents[2]))
ANCHOR_FILE = REPO / "character" / "bible" / "mouth-anchor.json"
REFERENCE = (REPO / "character" / "reference"
             / f"{canon.CHARACTER}-reference-master-v1.png")

CANVAS = 1024

# The edit region is the mask the reference-edit workflow is allowed to touch. It is
# wider and much taller than the REST mouth because a viseme opens the jaw downward:
# A is the maximum drop in the set and needs room below the resting lip line.
EDIT_PAD_X = 1.8        # multiple of mouth width, total
EDIT_PAD_UP = 0.8       # multiples of mouth height above the anchor
EDIT_PAD_DOWN = 2.6     # multiples of mouth height below the anchor

# Sanity bounds. A mouth outside these is a measurement error, not an unusual face.
MIN_MOUTH_WIDTH = 0.05
MAX_MOUTH_WIDTH = 0.40
MIN_MOUTH_HEIGHT = 0.01
MAX_MOUTH_HEIGHT = 0.25


def load():
    if not ANCHOR_FILE.exists():
        return None
    return json.loads(ANCHOR_FILE.read_text())


def validate(anchor, problems):
    if not MIN_MOUTH_WIDTH <= anchor["mouth_width"] <= MAX_MOUTH_WIDTH:
        problems.append(
            f"mouth_width {anchor['mouth_width']:.3f} is outside "
            f"{MIN_MOUTH_WIDTH}-{MAX_MOUTH_WIDTH} of image width - check the measurement")
    if not MIN_MOUTH_HEIGHT <= anchor["mouth_height"] <= MAX_MOUTH_HEIGHT:
        problems.append(
            f"mouth_height {anchor['mouth_height']:.3f} is outside "
            f"{MIN_MOUTH_HEIGHT}-{MAX_MOUTH_HEIGHT} of image height - check the measurement")
    if not 0.0 < anchor["anchor_x"] < 1.0 or not 0.0 < anchor["anchor_y"] < 1.0:
        problems.append("anchor is outside the image")
    if anchor["anchor_y"] < 0.5:
        problems.append(
            f"anchor_y {anchor['anchor_y']:.3f} puts the mouth in the upper half of the "
            "frame - the reference is a close-up, so this is almost certainly the eye line")


def normalize_box(box):
    left, top, right, bottom = box
    if right <= left or bottom <= top:
        return None
    return {
        "left": left / CANVAS,
        "top": top / CANVAS,
        "right": right / CANVAS,
        "bottom": bottom / CANVAS,
    }


def derive_edit_region(anchor):
    half_w = anchor["mouth_width"] * EDIT_PAD_X / 2
    return {
        "left": max(0.0, anchor["anchor_x"] - half_w),
        "top": max(0.0, anchor["anchor_y"] - anchor["mouth_height"] * EDIT_PAD_UP),
        "right": min(1.0, anchor["anchor_x"] + half_w),
        "bottom": min(1.0, anchor["anchor_y"] + anchor["mouth_height"] * EDIT_PAD_DOWN),
    }


def show():
    doc = load()
    if doc is None:
        print(f"error: {ANCHOR_FILE.relative_to(REPO)} not found", file=sys.stderr)
        return 1
    print(f"{ANCHOR_FILE.relative_to(REPO)}")
    print(f"  status: {doc.get('status')}")
    anchor = doc.get("anchor", {})
    if anchor.get("anchor_x") is None:
        print("  unmeasured - measure the REST mouth from the reference and run --box")
        return 0
    for key, value in anchor.items():
        print(f"  {key:<13} {value:.3f}  ({value * CANVAS:.0f}px at {CANVAS})")
    region = doc.get("edit_region") or {}
    if region:
        print("  edit_region:")
        for key, value in region.items():
            print(f"    {key:<11} {value:.3f}  ({value * CANVAS:.0f}px)")
    print(f"\n  measured_at: {doc.get('measured_at')}")
    return 0


def from_diff(reference, asset):
    """What moved between two images. A measurement aid, not a measurement."""
    result = imagecheck.changed_region(reference, asset)
    if result is None:
        print("error: Pillow is required, or the images differ in size", file=sys.stderr)
        return 1
    bbox, fraction = result
    if bbox is None:
        print("No pixels differ - the two images are identical.")
        return 0

    print(f"Changed region between\n  {reference}\n  {asset}\n")
    for key, value in bbox.items():
        print(f"  {key:<7} {value:.3f}  ({value * CANVAS:.0f}px at {CANVAS})")
    print(f"\n  changed area: {fraction:.2%} of the frame")
    print(f"  center:       x={((bbox['left'] + bbox['right']) / 2):.3f} "
          f"y={((bbox['top'] + bbox['bottom']) / 2):.3f}")
    print("\nThis is where the edit landed, not where the mouth is. Use it to sanity-check "
          "a\nmeasurement or to see what an edit actually touched - not as the anchor itself.")
    return 0


def write(box, edit_box):
    normalized = normalize_box(box)
    if normalized is None:
        print("error: --box must be LEFT TOP RIGHT BOTTOM with right > left and "
              "bottom > top", file=sys.stderr)
        return 2

    anchor = {
        "anchor_x": round((normalized["left"] + normalized["right"]) / 2, 3),
        "anchor_y": round((normalized["top"] + normalized["bottom"]) / 2, 3),
        "mouth_width": round(normalized["right"] - normalized["left"], 3),
        "mouth_height": round(normalized["bottom"] - normalized["top"], 3),
    }

    problems = []
    validate(anchor, problems)
    if problems:
        print("Measurement rejected:", file=sys.stderr)
        for problem in problems:
            print(f"  [FAIL] {problem}", file=sys.stderr)
        return 1

    if edit_box:
        region = normalize_box(edit_box)
        if region is None:
            print("error: --edit-region must be LEFT TOP RIGHT BOTTOM", file=sys.stderr)
            return 2
        if not (region["left"] <= normalized["left"] and region["top"] <= normalized["top"]
                and region["right"] >= normalized["right"]
                and region["bottom"] >= normalized["bottom"]):
            print("error: --edit-region does not contain the mouth box", file=sys.stderr)
            return 1
    else:
        region = derive_edit_region(anchor)

    doc = load() or {}
    doc.update({
        "$comment": "Measured from the approved reference (PHASE 4.3). See "
                    "character/bible/visual-spec.md section 4.",
        "character": canon.CHARACTER,
        "status": "measured",
        "version": 1,
        "measured_from": str(REFERENCE.relative_to(REPO)),
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "coordinate_space": {
            "normalized": True,
            "origin": "top-left",
            "reference_resolution": [CANVAS, CANVAS],
        },
        "anchor": anchor,
        "edit_region": {key: round(value, 3) for key, value in region.items()},
        "tolerances": {
            "anchor_drift_max_fraction_of_width": 0.005,
            "head_vertical_drift_max_fraction_of_height": 0.01,
        },
    })
    ANCHOR_FILE.parent.mkdir(parents=True, exist_ok=True)
    ANCHOR_FILE.write_text(json.dumps(doc, indent=2) + "\n")

    print(f"Wrote {ANCHOR_FILE.relative_to(REPO)}\n")
    for key, value in anchor.items():
        print(f"  {key:<13} {value:.3f}")
    print("  edit_region:")
    for key, value in doc["edit_region"].items():
        print(f"    {key:<11} {value:.3f}")
    print("\nNext: copy these into character/bible/visual-spec.md section 4 and set its "
          "status\ncells to LOCKED. Every viseme is now held to this anchor.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Record the mouth anchor and permitted edit region (PHASE 4.3).")
    parser.add_argument("--box", nargs=4, type=int, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
                        help="pixel coords of the REST mouth bounding box")
    parser.add_argument("--edit-region", nargs=4, type=int,
                        metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
                        help="pixel coords of the mask region; derived from --box if omitted")
    parser.add_argument("--show", action="store_true", help="print the current anchor")
    parser.add_argument("--from-diff", nargs=2, type=Path, metavar=("REFERENCE", "ASSET"),
                        help="report what changed between two images")
    args = parser.parse_args()

    modes = [bool(args.box), args.show, bool(args.from_diff)]
    if sum(modes) != 1:
        parser.error("use exactly one of --box, --show, --from-diff")
    if args.edit_region and not args.box:
        parser.error("--edit-region is only meaningful with --box")

    if args.show:
        return show()
    if args.from_diff:
        reference, asset = args.from_diff
        for path in (reference, asset):
            if not path.exists():
                print(f"error: {path} not found", file=sys.stderr)
                return 2
        return from_diff(reference, asset)
    return write(args.box, args.edit_region)


if __name__ == "__main__":
    sys.exit(main())
