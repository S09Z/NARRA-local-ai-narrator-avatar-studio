#!/usr/bin/env python3
"""Validate the narrator compositions (PHASE 5.3).

A composition is a recipe over the asset layers - pose, expression, and a mouth
mode - not an asset in its own right (DECISIONS.md ADR-004). It is validated
here rather than at animation time because a state that names a nonexistent pose
or an impossible layer combination should fail now, not in PHASE 8.

The rule this exists to enforce: an open-mouth expression cannot host a viseme
track. The mouth is already spent, so compositing a viseme over it would render
two mouths.

Usage:
    validate_compositions.py                 validate the default file
    validate_compositions.py <file.json>     validate a specific file

Exit code 0 = valid, 1 = invalid, 2 = usage error.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import canon                                          # noqa: E402
from imagecheck import FAIL, PASS, WARN, Report       # noqa: E402

REPO = Path(os.environ.get("NARRA_REPO", Path(__file__).resolve().parents[2]))
DEFAULT = REPO / "character" / "compositions" / "narrator-states.json"
POSE_PROMPTS = REPO / "prompts" / "poses"


def pose_camera_class(pose):
    """The camera class the pose prompt declares, or None if there is no prompt."""
    matches = sorted(POSE_PROMPTS.glob(f"{pose}-v*.md"))
    if not matches:
        return None
    for line in matches[-1].read_text().splitlines():
        if line.startswith("camera_class:"):
            return line.split(":", 1)[1].strip()
        if line.strip() == "---" and "camera_class" not in line:
            continue
    return None


def check_state(name, state, report):
    prefix = f"{name}/"

    if not isinstance(state, dict):
        report.add(FAIL, prefix + "shape", "state is not an object")
        return

    for field in ("description", "pose", "camera_class", "expression", "mouth"):
        if not state.get(field):
            report.add(FAIL, prefix + field, "missing or empty")

    pose = state.get("pose")
    if pose and canon.index_of("pose", pose) is None:
        report.add(FAIL, prefix + "pose",
                   f"{pose!r} is not in the canonical pose set - "
                   f"{', '.join(canon.POSES)}")
    elif pose:
        report.add(PASS, prefix + "pose", pose)

    expression = state.get("expression")
    if expression and canon.index_of("expression", expression) is None:
        report.add(FAIL, prefix + "expression",
                   f"{expression!r} is not in the canonical expression set")
    elif expression:
        report.add(PASS, prefix + "expression", expression)

    camera_class = state.get("camera_class")
    if camera_class and camera_class not in canon.CAMERA_CLASSES:
        report.add(FAIL, prefix + "camera_class",
                   f"{camera_class!r} is not one of "
                   f"{', '.join(sorted(canon.CAMERA_CLASSES))}")
    elif camera_class and pose:
        declared = pose_camera_class(pose)
        if declared is None:
            report.add(WARN, prefix + "camera_class",
                       f"no pose prompt for {pose!r} to cross-check against")
        elif declared != camera_class:
            report.add(FAIL, prefix + "camera_class",
                       f"{camera_class!r} but the {pose!r} pose prompt declares "
                       f"{declared!r} - the composition and the asset disagree "
                       "about the framing")
        else:
            report.add(PASS, prefix + "camera_class", f"{camera_class} (matches the pose prompt)")

    mouth = state.get("mouth")
    if mouth and mouth not in canon.MOUTH_MODES:
        report.add(FAIL, prefix + "mouth",
                   f"{mouth!r} is not one of {', '.join(sorted(canon.MOUTH_MODES))}")
        return

    idle = state.get("idle_viseme")
    if mouth == "viseme-track":
        if expression in canon.OPEN_MOUTH_EXPRESSIONS:
            report.add(FAIL, prefix + "mouth",
                       f"a viseme track cannot be composited over the {expression!r} "
                       "expression - it already carries an open mouth, so the result "
                       "would render two mouths (ASSET_SPEC.md 6, ADR-004)")
        else:
            report.add(PASS, prefix + "mouth",
                       f"viseme-track over the REST-mouth {expression!r} expression")
        if not idle:
            report.add(FAIL, prefix + "idle_viseme",
                       "a viseme-track state needs an idle_viseme to return to")
        elif canon.index_of("viseme", idle) is None:
            report.add(FAIL, prefix + "idle_viseme",
                       f"{idle!r} is not in the canonical viseme set")
    elif mouth == "static":
        report.add(PASS, prefix + "mouth", f"static mouth from the {expression!r} expression")
        if idle:
            report.add(WARN, prefix + "idle_viseme",
                       f"{idle!r} recorded but the mouth is static - it will be ignored")


def validate(path):
    report = Report()
    print(f"Validating {path}\n")

    try:
        document = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        print(f"  [FAIL] json  invalid: {exc}")
        return 1

    if document.get("character") != canon.CHARACTER:
        report.add(FAIL, "character",
                   f"{document.get('character')!r}, expected {canon.CHARACTER!r}")
    else:
        report.add(PASS, "character", canon.CHARACTER)

    states = document.get("states")
    if not isinstance(states, dict) or not states:
        report.add(FAIL, "states", "missing or empty")
        print(report.render())
        return 1

    missing = [name for name in canon.NARRATOR_STATES if name not in states]
    if missing:
        report.add(FAIL, "states/required",
                   f"missing: {', '.join(missing)} (PLAN.md 5.3)")
    else:
        report.add(PASS, "states/required",
                   f"all {len(canon.NARRATOR_STATES)} required states present")

    for name in sorted(states):
        check_state(name, states[name], report)

    print(report.render())
    counts = report.counts()
    if report.failed():
        print(f"\nFAILED - {counts.get(FAIL, 0)} problem(s). These states are not usable.")
        return 1
    print(f"\n{len(states)} composition(s) valid.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Validate the narrator compositions (PHASE 5.3).")
    parser.add_argument("file", nargs="?", type=Path, default=DEFAULT)
    args = parser.parse_args()

    if not args.file.exists():
        print(f"error: {args.file} not found", file=sys.stderr)
        return 2
    return validate(args.file)


if __name__ == "__main__":
    sys.exit(main())
