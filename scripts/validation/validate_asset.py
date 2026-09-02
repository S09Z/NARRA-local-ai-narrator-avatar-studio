#!/usr/bin/env python3
"""Validate a generated character asset against ASSET_SPEC.md (PHASE 3.4).

Checks everything a machine can check - naming, format, alpha, metadata
completeness, seed derivation, and drift against the reference - and then prints
the checklist of things only a person can judge. The two halves are kept visibly
separate so an automated PASS is never mistaken for an approval.

Usage:
    validate_asset.py <asset.png>              validate one asset
    validate_asset.py <asset.png> --record     also write metadata/validation/<stem>.json
    validate_asset.py --set expression         check a whole set for completeness

Exit code 0 = automated checks passed, 1 = at least one FAIL, 2 = usage error.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import canon                                                  # noqa: E402
import imagecheck                                             # noqa: E402
from imagecheck import FAIL, PASS, SKIP, WARN, Report, sha256  # noqa: E402

REPO = Path(os.environ.get("NARRA_REPO", Path(__file__).resolve().parents[2]))
BIBLE = REPO / "character" / "bible"
ANCHOR_FILE = BIBLE / "mouth-anchor.json"
VALIDATION_DIR = REPO / "metadata" / "validation"

ASSET_DIRS = {
    "expression": REPO / "character" / "expressions",
    "viseme": REPO / "character" / "visemes",
    "pose": REPO / "character" / "poses",
}

# ASSET_SPEC.md section 11
MANDATORY_FIELDS = [
    "character", "asset_type", "asset_name", "version", "file", "reference",
    "model", "workflow", "prompt.master_version", "prompt.asset_prompt_version",
    "generation.seed", "generation.resolution", "validation.status", "generated_at",
]

# ASSET_SPEC.md section 9
ANCHOR_DRIFT_MAX = 0.005
HEAD_DRIFT_MAX = 0.01

# PLAN.md section 3.4 - the half a script cannot do.
HUMAN_CHECKLIST = {
    "identity": [
        "Same person as the reference - face proportions and head shape",
        "Eye shape, eye color, and eye position unchanged",
        "Eyebrow shape and thickness unchanged (position may change for an expression)",
        "Hairstyle, hair color, and hair part unchanged",
        "Skin tone unchanged",
        "Clothing and accessories unchanged",
    ],
    "render": [
        "Art style and line style consistent with the reference",
        "Lighting direction unchanged - the shadow side did not flip",
        "No photorealistic drift, no added text, no artifacts",
    ],
    "expression": [
        "Target expression legible at 256px in a contact sheet",
        "Distinct from every other expression in the set",
        "Mouth is at REST unless this expression is defined by an open mouth",
    ],
    "viseme": [
        "Only the mouth changed - eyes, eyebrows, gaze, head angle identical to REST",
        "MBP is distinguishable from REST side by side at 256px",
    ],
    "pose": [
        "Hands fully in frame or fully out of frame - never cropped mid-hand",
        "Head size consistent with the declared camera class",
    ],
}


def dig(data, dotted):
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def pose_camera_class(pose):
    """The camera class the pose prompt declares, or None if there is no prompt."""
    for path in sorted((REPO / "prompts" / "poses").glob(f"{pose}-v*.md")):
        for line in path.read_text().splitlines():
            if line.startswith("camera_class:"):
                return line.split(":", 1)[1].strip()
    return None


def reference_path():
    versioned = REPO / "character" / "reference" / f"{canon.CHARACTER}-reference-master-v1.png"
    return versioned if versioned.exists() else None


def check_naming(path, report):
    """ASSET_SPEC 5. Returns the parsed filename fields, or None."""
    fields = canon.parse_filename(path.stem)
    if fields is None:
        report.add(FAIL, "naming/pattern",
                   f"{path.name} does not match <character>-<type>-<name>-v<version>.png "
                   "(ASSET_SPEC 5)")
        return None
    report.add(PASS, "naming/pattern", path.name)

    if fields["character"] != canon.CHARACTER:
        report.add(FAIL, "naming/character",
                   f"{fields['character']!r}, expected {canon.CHARACTER!r}")
    if fields["asset_type"] not in ASSET_DIRS:
        report.add(FAIL, "naming/type",
                   f"{fields['asset_type']!r}, expected one of {', '.join(ASSET_DIRS)}")
        return fields

    if canon.index_of(fields["asset_type"], fields["name"]) is None:
        report.add(FAIL, "naming/canonical",
                   f"{fields['name']!r} is not in the canonical {fields['asset_type']} set "
                   f"- {', '.join(canon.CANONICAL[fields['asset_type']])}")
    else:
        report.add(PASS, "naming/canonical",
                   f"{canon.canonical_name(fields['asset_type'], fields['name'])}")

    expected_dir = ASSET_DIRS[fields["asset_type"]]
    if path.parent.resolve() != expected_dir.resolve():
        report.add(WARN, "naming/location",
                   f"not in {expected_dir.relative_to(REPO)} - approved assets live there "
                   "(ASSET_SPEC 6-8)")
    return fields


def check_sidecar(path, fields, report):
    """ASSET_SPEC 11. Returns the sidecar dict, or None."""
    sidecar_path = path.with_suffix(".json")
    if not sidecar_path.exists():
        report.add(FAIL, "metadata/sidecar",
                   f"{sidecar_path.name} missing - an asset without metadata is not "
                   "reproducible and cannot be locked (ASSET_SPEC 11)")
        return None
    try:
        data = json.loads(sidecar_path.read_text())
    except json.JSONDecodeError as exc:
        report.add(FAIL, "metadata/sidecar", f"invalid JSON: {exc}")
        return None
    report.add(PASS, "metadata/sidecar", sidecar_path.name)

    missing = [field for field in MANDATORY_FIELDS if dig(data, field) in (None, "")]
    if missing:
        report.add(FAIL, "metadata/mandatory",
                   f"missing or empty: {', '.join(missing)} (ASSET_SPEC 11)")
    else:
        report.add(PASS, "metadata/mandatory", f"all {len(MANDATORY_FIELDS)} fields present")

    if fields:
        expected_name = canon.canonical_name(fields["asset_type"], fields["name"])
        pairs = [
            ("character", fields["character"]),
            ("asset_type", fields["asset_type"]),
            ("asset_name", expected_name),
            ("version", int(fields["version"])),
        ]
        mismatched = [f"{key}={data.get(key)!r} != {value!r}"
                      for key, value in pairs if data.get(key) != value]
        if mismatched:
            report.add(FAIL, "metadata/filename-agreement", "; ".join(mismatched))
        else:
            report.add(PASS, "metadata/filename-agreement", "metadata matches the filename")

        if fields["asset_type"] == "pose":
            # ASSET_SPEC 8: pose name AND camera class are both recorded.
            recorded_class = data.get("camera_class")
            declared = pose_camera_class(fields["name"])
            if not recorded_class:
                report.add(FAIL, "metadata/camera-class",
                           "pose metadata must record camera_class (ASSET_SPEC 8)")
            elif recorded_class not in canon.CAMERA_CLASSES:
                report.add(FAIL, "metadata/camera-class",
                           f"{recorded_class!r} is not one of "
                           f"{', '.join(sorted(canon.CAMERA_CLASSES))}")
            elif declared and declared != recorded_class:
                report.add(FAIL, "metadata/camera-class",
                           f"{recorded_class!r} but the {fields['name']!r} pose prompt "
                           f"declares {declared!r} - the asset was framed differently "
                           "from the prompt it records")
            else:
                report.add(PASS, "metadata/camera-class", recorded_class)

        seed = dig(data, "generation.seed")
        try:
            expected_seed = canon.derive_seed(fields["asset_type"], fields["name"])
        except canon.CanonError:
            expected_seed = None
        if expected_seed is None:
            report.add(SKIP, "metadata/seed", "asset is outside the canonical set")
        elif seed != expected_seed:
            report.add(FAIL, "metadata/seed",
                       f"{seed} recorded, {expected_seed} derived from the canonical index "
                       "(prompts/README.md 4)")
        else:
            report.add(PASS, "metadata/seed", str(seed))

    resolution = dig(data, "generation.resolution")
    if resolution != list(imagecheck.REQUIRED_SIZE):
        report.add(FAIL, "metadata/resolution",
                   f"{resolution} recorded, expected {list(imagecheck.REQUIRED_SIZE)}")
    else:
        report.add(PASS, "metadata/resolution", f"{resolution[0]}x{resolution[1]}")

    recorded = data.get("sha256")
    if recorded and recorded != sha256(path):
        report.add(FAIL, "metadata/sha256",
                   "recorded hash does not match the image - the asset changed after "
                   "its metadata was written")
    elif recorded:
        report.add(PASS, "metadata/sha256", "matches the image")

    reference = data.get("reference")
    master = reference_path()
    if not reference:
        report.add(FAIL, "metadata/reference", "no reference recorded (ASSET_SPEC 11)")
    elif master is None:
        report.add(SKIP, "metadata/reference", "no reference imported yet to compare against")
    elif Path(reference).name != master.name:
        report.add(FAIL, "metadata/reference",
                   f"{reference} is not the current reference {master.name} - assets "
                   "derived from different references will not composite")
    else:
        report.add(PASS, "metadata/reference", master.name)

    return data


def check_drift(path, data, report):
    """Head and mouth-anchor drift against the reference (ASSET_SPEC 9)."""
    master = reference_path()
    if master is None:
        report.add(SKIP, "drift/head", "no reference imported")
        report.add(SKIP, "drift/anchor", "no reference imported")
        return

    asset_box = imagecheck.silhouette_bbox(path)
    reference_box = imagecheck.silhouette_bbox(master)
    if asset_box is None or reference_box is None:
        report.add(SKIP, "drift/head", "Pillow not installed, or the cutout is empty")
    else:
        drift = abs(asset_box["top"] - reference_box["top"])
        if drift <= HEAD_DRIFT_MAX:
            report.add(PASS, "drift/head",
                       f"silhouette top moved {drift:.3%} of height (max "
                       f"{HEAD_DRIFT_MAX:.0%}, {drift * 1024:.1f}px at 1024)")
        else:
            report.add(FAIL, "drift/head",
                       f"silhouette top moved {drift:.3%} of height, max "
                       f"{HEAD_DRIFT_MAX:.0%} - outside tolerance regardless of how good "
                       "the asset looks (ASSET_SPEC 9)")

    if not ANCHOR_FILE.exists():
        report.add(SKIP, "drift/anchor", "character/bible/mouth-anchor.json missing")
        return
    anchor_doc = json.loads(ANCHOR_FILE.read_text())
    baseline = anchor_doc.get("anchor", {})
    if anchor_doc.get("status") != "measured" or baseline.get("anchor_x") is None:
        report.add(SKIP, "drift/anchor",
                   "mouth anchor is unmeasured - measured in PHASE 4.3 "
                   "(character/bible/visual-spec.md 4)")
        return

    measured = (data or {}).get("mouth_anchor") or {}
    if measured.get("anchor_x") is None:
        report.add(FAIL, "drift/anchor",
                   "asset metadata records no mouth_anchor, so drift cannot be detected "
                   "(ASSET_SPEC 9)")
        return

    dx = abs(measured["anchor_x"] - baseline["anchor_x"])
    dy = abs(measured["anchor_y"] - baseline["anchor_y"])
    drift = max(dx, dy)
    if drift <= ANCHOR_DRIFT_MAX:
        report.add(PASS, "drift/anchor",
                   f"{drift:.3%} of width ({drift * 1024:.1f}px at 1024)")
    else:
        report.add(FAIL, "drift/anchor",
                   f"{drift:.3%} of width, max {ANCHOR_DRIFT_MAX:.1%} - the viseme layer "
                   "will not composite onto this asset (ASSET_SPEC 9)")


def check_containment(path, fields, report):
    """PHASE 4.5: did the edit stay inside the region it was allowed to touch?

    "Change only the mouth" is the strictest rule in the project and, until now, was
    only checkable by eye. Diffing the asset against the reference turns it into a
    measurement: whatever moved either falls inside the recorded edit region or it
    does not.
    """
    asset_type = (fields or {}).get("asset_type")
    if asset_type != "viseme":
        report.add(SKIP, "containment/region",
                   "only visemes have a recorded edit region (PHASE 4.3)")
        return

    master = reference_path()
    if master is None:
        report.add(SKIP, "containment/region", "no reference imported")
        return
    if not ANCHOR_FILE.exists():
        report.add(SKIP, "containment/region", "character/bible/mouth-anchor.json missing")
        return

    anchor_doc = json.loads(ANCHOR_FILE.read_text())
    region = anchor_doc.get("edit_region")
    if anchor_doc.get("status") != "measured" or not region:
        report.add(SKIP, "containment/region",
                   "edit region unmeasured - set it with scripts/utilities/measure_anchor.py")
        return

    result = imagecheck.changed_region(master, path)
    if result is None:
        report.add(SKIP, "containment/region", "Pillow not installed, or sizes differ")
        return

    bbox, fraction = result
    if bbox is None:
        report.add(WARN, "containment/region",
                   "no pixels differ from the reference - this asset is a copy of it")
        return

    outside = []
    if bbox["left"] < region["left"]:
        outside.append(f"left by {(region['left'] - bbox['left']) * 1024:.0f}px")
    if bbox["top"] < region["top"]:
        outside.append(f"above by {(region['top'] - bbox['top']) * 1024:.0f}px")
    if bbox["right"] > region["right"]:
        outside.append(f"right by {(bbox['right'] - region['right']) * 1024:.0f}px")
    if bbox["bottom"] > region["bottom"]:
        outside.append(f"below by {(bbox['bottom'] - region['bottom']) * 1024:.0f}px")

    if outside:
        report.add(FAIL, "containment/region",
                   f"the edit escaped the mouth region: {', '.join(outside)}. Something "
                   "other than the mouth changed (PROMPT_GUIDE.md 6)")
    else:
        report.add(PASS, "containment/region",
                   f"edit confined to the mouth region, {fraction:.2%} of the frame changed")


def human_checklist(asset_type):
    groups = ["identity", "render"]
    if asset_type in HUMAN_CHECKLIST:
        groups.append(asset_type)
    lines = []
    for group in groups:
        lines.append(f"  {group}:")
        lines.extend(f"    [ ] {item}" for item in HUMAN_CHECKLIST[group])
    return "\n".join(lines)


def record(path, fields, report, data):
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    target = VALIDATION_DIR / f"{path.stem}.json"
    payload = {
        "asset": str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path),
        "asset_type": (fields or {}).get("asset_type"),
        "asset_name": (data or {}).get("asset_name"),
        "validated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "automated": {
            "status": "failed" if report.failed() else "passed",
            "counts": report.counts(),
            "checks": [
                {"level": level, "check": name, "detail": detail}
                for level, name, detail in report.rows
            ],
        },
        "human_review": {
            "status": "pending",
            "reviewer": "",
            "notes": "",
        },
        "overall": "failed" if report.failed() else "pending-human-review",
    }
    target.write_text(json.dumps(payload, indent=2) + "\n")
    return target


def validate_one(path, do_record):
    report = Report()
    print(f"Validating {path}\n")

    fields = check_naming(path, report)
    if imagecheck.check_header(path, report):
        imagecheck.check_pixels(path, report)
    data = check_sidecar(path, fields, report)
    check_drift(path, data, report)
    check_containment(path, fields, report)

    print(report.render())

    if do_record:
        target = record(path, fields, report, data)
        print(f"\nRecorded: {target.relative_to(REPO)}")

    if report.failed():
        print("\nFAILED - asset does not meet ASSET_SPEC. Regenerate; do not lock it.")
        return 1

    asset_type = (fields or {}).get("asset_type", "")
    print("\nAutomated checks passed. NOT an approval - the identity checks in "
          "ASSET_SPEC 10 are visual:\n")
    print(human_checklist(asset_type))
    print("\nAn asset is APPROVED only when every box above is also ticked.")
    return 0


def validate_set(asset_type):
    """PHASE 3.5 / 4.6 / 5: is the set complete and free of strays?"""
    if asset_type not in ASSET_DIRS:
        print(f"error: unknown set {asset_type!r}", file=sys.stderr)
        return 2

    directory = ASSET_DIRS[asset_type]
    expected = canon.CANONICAL[asset_type]
    print(f"Checking the {asset_type} set in {directory.relative_to(REPO)}\n")

    found = {}
    strays = []
    for path in sorted(directory.glob("*.png")):
        fields = canon.parse_filename(path.stem)
        if fields is None or canon.index_of(asset_type, fields["name"]) is None:
            strays.append(path.name)
            continue
        found[canon.canonical_name(asset_type, fields["name"])] = path

    missing = [name for name in expected if name not in found]
    for name in expected:
        marker = "OK     " if name in found else "MISSING"
        suffix = ""
        if asset_type == "pose":
            # ASSET_SPEC 8: head size is consistent within a camera class, so the
            # class each asset belongs to has to be visible when reviewing the set.
            declared = pose_camera_class(name)
            suffix = f"  [{declared or 'no prompt'}]"
        print(f"  [{marker}] {name}{suffix}")
    for name in strays:
        print(f"  [STRAY  ] {name}")

    print(f"\n{len(found)}/{len(expected)} present.")
    if missing:
        print(f"Missing: {', '.join(missing)}")
    if strays:
        print(f"Not in the canonical {asset_type} set: {', '.join(strays)}")
    if missing or strays:
        print(f"\nThe {asset_type} set is not complete. It cannot be locked.")
        return 1

    print(f"\nThe {asset_type} set is complete. Validate each asset individually "
          "before locking.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Validate a generated character asset against ASSET_SPEC.md (PHASE 3.4).")
    parser.add_argument("asset", nargs="?", type=Path, help="asset PNG to validate")
    parser.add_argument("--record", action="store_true",
                        help="write the result to metadata/validation/")
    parser.add_argument("--set", dest="asset_set",
                        help="check a whole set for completeness: expression, viseme, pose")
    args = parser.parse_args()

    if args.asset_set:
        if args.asset:
            parser.error("--set checks a whole set; do not also name an asset")
        return validate_set(args.asset_set)

    if not args.asset:
        parser.error("name an asset PNG, or use --set")
    if not args.asset.exists():
        print(f"error: {args.asset} not found", file=sys.stderr)
        return 2

    return validate_one(args.asset, args.record)


if __name__ == "__main__":
    sys.exit(main())
