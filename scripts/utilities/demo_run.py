#!/usr/bin/env python3
"""Guided first run of the pipeline (development tooling).

A newcomer's first question is not "what is the plan" - PLAN.md answers that - but
"what can I run right now, and where does it stop?" Answering that by hand means
collecting eight commands out of four documents and then knowing which failures are
work waiting for a person and which are the GPU this machine does not have.

This walks those commands in order, in one pass. It generates nothing, writes
nothing, and installs nothing. Every step prints the real command before running it,
so the tour and the manual procedure in GUIDELINE.md cannot drift apart.

Each step reports one of three outcomes:

    OK       the step's check passes today
    TODO     work waiting for a person, doable on this machine
    BLOCKED  waiting on something this machine does not have (PHASE 0, GPU)

Usage:
    demo_run.py                 run every step in order
    demo_run.py --list          show the steps and stop
    demo_run.py --step KEY      run one step
    demo_run.py --verbose       include the full output of every command
    demo_run.py --json          the same results as JSON

Exit code 0 = the walkthrough ran, whatever the steps reported; 2 = usage error.
A first run that fails the build is a tour wearing the wrong name.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("NARRA_REPO", Path(__file__).resolve().parents[2]))

BIBLE_FILES = [REPO / "character" / "bible" / "character-bible.md",
               REPO / "character" / "bible" / "visual-spec.md"]
ANCHOR_FILE = REPO / "character" / "bible" / "mouth-anchor.json"

VALIDATE_REFERENCE = "scripts/validation/validate_reference.py"
COMPILE_PROMPT = "scripts/generation/compile_prompt.py"
LOCK_LIBRARY = "scripts/validation/lock_library.py"
STATUS = "scripts/utilities/status.py"
MEASURE_ANCHOR = "scripts/utilities/measure_anchor.py"

SAMPLE_PROMPT = "visemes/mbp-v1.0.md"
SET_ORDER = ["expression", "viseme", "pose"]

OK, TODO, BLOCKED = "OK", "TODO", "BLOCKED"

MIN_PYTHON = (3, 10)
# An unfilled bible slot survives compilation as <...>; FLUX would invent the contents.
PLACEHOLDER_RE = re.compile(r"<[^<>\n]{4,}>")
PREVIEW_LINES = 12


def run(*argv):
    """Run one repository script. Returns (returncode, combined output)."""
    command = [sys.executable] + [str(part) for part in argv]
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=300,
                              cwd=str(REPO),
                              env=dict(os.environ, NARRA_REPO=str(REPO)))
    except (OSError, subprocess.SubprocessError) as error:
        return None, f"{type(error).__name__}: {error}"
    return done.returncode, (done.stdout + done.stderr).rstrip("\n")


def shown(*argv):
    """The command as a reader would type it."""
    return " ".join(["python3"] + [str(part) for part in argv])


def result(state, summary, detail=(), command=None, output=""):
    return {"state": state, "summary": summary, "detail": list(detail),
            "command": command, "output": output}


# --- steps ----------------------------------------------------------------

def step_toolchain():
    """PHASE 0.1 - can any of the rest of this even run."""
    version = ".".join(str(part) for part in sys.version_info[:3])
    try:
        import PIL
        pillow = PIL.__version__
    except ImportError:
        pillow = None

    detail = [f"python  {version}  ({sys.executable})",
              f"Pillow  {pillow or 'not installed'}",
              f"git     {'present' if shutil.which('git') else 'not on PATH'}"]
    problems = []
    if sys.version_info < MIN_PYTHON:
        problems.append(f"python {version} is below the "
                        f"{'.'.join(str(p) for p in MIN_PYTHON)} pyproject.toml requires "
                        "- run `make install` and rerun with .venv/bin/python")
    if pillow is None:
        problems.append("Pillow missing - every pixel check reports SKIP, never PASS "
                        "(scripts/lib/imagecheck.py) - run `make install`")
    if problems:
        return result(TODO, "interpreter or dependencies not ready", detail + problems)
    return result(OK, f"python {version}, Pillow {pillow}", detail)


def step_reference():
    """PHASE 1.1 - the canonical reference is imported and still matches its sidecar."""
    argv = (VALIDATE_REFERENCE, "--check-imported")
    code, output = run(*argv)
    if code == 0:
        return result(OK, "reference imported, sidecars match", [
            "the six visual checks in the output are still yours to confirm by eye"],
            shown(*argv), output)
    return result(TODO, "no verified reference in character/reference/", [
        "import a candidate:",
        f"  {shown(VALIDATE_REFERENCE, 'assets/input/candidate.png')}",
        f"  {shown(VALIDATE_REFERENCE, 'assets/input/candidate.png', '--import')}"],
        shown(*argv), output)


def step_bible():
    """PHASE 1.2-1.3 - the CHARACTER block every later prompt embeds."""
    detail, unfilled, missing = [], 0, []
    for path in BIBLE_FILES:
        if not path.exists():
            missing.append(path.name)
            continue
        count = path.read_text(encoding="utf-8").count("TBD")
        unfilled += count
        detail.append(f"{path.name:22} {count} TBD")
    if missing:
        return result(TODO, f"missing: {', '.join(missing)}", detail)
    if unfilled:
        return result(TODO, f"{unfilled} fields still TBD", detail + [
            "fill them from the reference image - an unfilled field is a field FLUX invents"])
    return result(OK, "no TBD fields left", detail)


def step_anchor():
    """PHASE 4.3 - the one measurement every viseme is held to."""
    if not ANCHOR_FILE.exists():
        return result(TODO, "mouth-anchor.json missing", [str(ANCHOR_FILE)])
    try:
        doc = json.loads(ANCHOR_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return result(TODO, f"mouth-anchor.json unreadable: {error}")

    anchor = doc.get("anchor") or {}
    detail = [f"status  {doc.get('status')}",
              f"anchor  " + ", ".join(f"{key}={anchor.get(key)}" for key in sorted(anchor))]
    if doc.get("status") == "measured" and all(anchor.get(key) is not None for key in anchor):
        return result(OK, "measured", detail)
    return result(TODO, "unmeasured - blocks the PHASE 6 gate", detail + [
        "measure the REST mouth box on the reference, then:",
        f"  {shown(MEASURE_ANCHOR, '--box', 'LEFT', 'TOP', 'RIGHT', 'BOTTOM')}"])


def step_prompts():
    """PHASE 2 - every prompt source is structurally sound before any of it is generated."""
    argv = (COMPILE_PROMPT, "--lint")
    code, output = run(*argv)
    if code == 0:
        return result(OK, "every prompt under prompts/ lints", [], shown(*argv), output)
    return result(TODO, "prompt lint fails", [], shown(*argv), output)


def step_compile():
    """PHASE 2.2 - what a generation would actually be handed. The demo's artefact."""
    argv = (COMPILE_PROMPT, SAMPLE_PROMPT)
    code, output = run(*argv)
    if code != 0:
        return result(TODO, f"{SAMPLE_PROMPT} does not compile", [], shown(*argv), output)

    placeholders = len(PLACEHOLDER_RE.findall(output))
    preview = output.splitlines()[:PREVIEW_LINES]
    preview.append(f"... {len(output.splitlines()) - len(preview)} more lines")
    if placeholders:
        return result(TODO, f"compiles, but carries {placeholders} unfilled bible slots",
                      preview + ["", "each <...> above is a field FLUX would invent - "
                                 "step 3 is what closes them"], shown(*argv), output)
    return result(OK, "compiles with no unfilled slots", preview, shown(*argv), output)


def step_generate():
    """PHASE 1.4, 3-5 - the wall. Generation needs ComfyUI and the GPU, not this script."""
    argv = (STATUS, "--json", "--no-gate")
    code, output = run(*argv)
    if code != 0:
        return result(BLOCKED, "library state unreadable", [], shown(*argv), output)
    try:
        library = json.loads(output)["library"]
    except (json.JSONDecodeError, KeyError) as error:
        return result(BLOCKED, f"library state unreadable: {error}", [], shown(*argv), output)

    detail, missing = [], 0
    for asset_type in SET_ORDER:
        entry = library[asset_type]
        missing += len(entry["missing"])
        detail.append(f"{asset_type + 's':14} {entry['present']} / {entry['required']}")
    detail.append(f"{'QC sign-offs':14} {library['approvals']['approved']} approved")
    if missing == 0:
        return result(OK, "every canonical asset is present", detail, shown(*argv))
    return result(BLOCKED, f"{missing} of {library['total_required']} assets not generated",
                  detail + ["generation runs on the RTX 5070 machine, not here:",
                            "  ComfyUI + FLUX.2 Klein 4B (docs/operations/phase-0-environment-setup.md)",
                            "  then tests/assets/phase1-baseline.md before any set"],
                  shown(*argv))


def step_gate():
    """PHASE 6 - the gate that decides whether anything downstream may start."""
    argv = (LOCK_LIBRARY,)
    code, output = run(*argv)
    if code == 0:
        return result(OK, "PHASE 6 gate passes", [
            "lock it: " + shown(LOCK_LIBRARY, "--lock", "--by", '"name"')],
            shown(*argv), output)
    problems = [line.strip() for line in output.splitlines() if "[FAIL]" in line]
    return result(BLOCKED, f"gate fails - {len(problems)} blocking problem(s)",
                  problems[:5] + (["..."] if len(problems) > 5 else []) +
                  ["PHASE 7-10 stay blocked until this passes (CLAUDE.md phase gate)"],
                  shown(*argv), output)


STEPS = [
    ("toolchain", "PHASE 0",     "Toolchain",        "the checks below can run at all",           step_toolchain),
    ("reference", "PHASE 1.1",   "Canonical reference", "one source of truth, verified against its sidecar", step_reference),
    ("bible",     "PHASE 1.2-3", "Character bible",  "the CHARACTER block every prompt embeds",   step_bible),
    ("anchor",    "PHASE 4.3",   "Mouth anchor",     "the measurement every viseme is held to",   step_anchor),
    ("prompts",   "PHASE 2",     "Prompt sources",   "38 prompts are structurally sound",         step_prompts),
    ("compile",   "PHASE 2.2",   "Compiled prompt",  "what a generation would actually be handed", step_compile),
    ("generate",  "PHASE 1.4-5", "Asset generation", "the 38 images exist",                       step_generate),
    ("gate",      "PHASE 6",     "Production gate",  "the library may be locked and used",        step_gate),
]


def walk(keys=None):
    chosen = [step for step in STEPS if keys is None or step[0] in keys]
    results = []
    for number, (key, phase, title, proves, runner) in enumerate(chosen, start=1):
        outcome = runner()
        outcome.update({"key": key, "phase": phase, "title": title, "proves": proves,
                        "number": number, "of": len(chosen)})
        results.append(outcome)
    return results


def next_action(results):
    """The single thing this state is asking for. A pointer, not a plan."""
    for outcome in results:
        if outcome["state"] == TODO:
            return f"step {outcome['number']} ({outcome['key']}) - {outcome['summary']}"
    for outcome in results:
        if outcome["state"] == BLOCKED:
            return f"step {outcome['number']} ({outcome['key']}) - {outcome['summary']}"
    return "nothing - every step in the walkthrough passes"


def render(results, verbose=False):
    lines = ["", "NARRA - demo first run", f"  repo  {REPO}", ""]
    lines += ["  Nothing is generated, written, or installed. Every command is printed",
              "  before it runs. Full procedure: GUIDELINE.md", ""]

    for outcome in results:
        lines.append(f"  [{outcome['number']}/{outcome['of']}] {outcome['title']:20} "
                     f"{outcome['phase']}")
        lines.append(f"        proves   {outcome['proves']}")
        if outcome["command"]:
            lines.append(f"        run      {outcome['command']}")
        lines.append(f"        {outcome['state']:8} {outcome['summary']}")
        for line in outcome["detail"]:
            lines.append(f"                 {line}")
        if verbose and outcome["output"]:
            lines.append("        output")
            lines += [f"          | {line}" for line in outcome["output"].splitlines()]
        lines.append("")

    tally = {state: sum(1 for r in results if r["state"] == state)
             for state in (OK, TODO, BLOCKED)}
    lines.append("Summary")
    lines.append("  " + "   ".join(f"{state} {count}" for state, count in tally.items()))
    lines.append("")
    lines.append("Next")
    lines.append(f"  {next_action(results)}")
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Guided first run: walk the pipeline without generating anything.")
    parser.add_argument("--list", action="store_true", dest="list_steps",
                        help="show the steps and stop")
    parser.add_argument("--step", action="append", metavar="KEY",
                        help="run one step (repeatable)")
    parser.add_argument("--verbose", action="store_true",
                        help="include the full output of every command")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="emit the results as JSON")
    args = parser.parse_args()

    if args.list_steps:
        for key, phase, title, proves, _ in STEPS:
            print(f"  {key:10} {phase:12} {title:20} {proves}")
        return 0

    known = {step[0] for step in STEPS}
    unknown = sorted(set(args.step or []) - known)
    if unknown:
        parser.error(f"unknown step(s): {', '.join(unknown)}; "
                     f"choose from {', '.join(sorted(known))}")

    results = walk(set(args.step) if args.step else None)
    if args.as_json:
        print(json.dumps({"repo": str(REPO), "steps": results,
                          "next": next_action(results)}, indent=2))
    else:
        print(render(results, verbose=args.verbose))
    return 0


if __name__ == "__main__":
    sys.exit(main())
