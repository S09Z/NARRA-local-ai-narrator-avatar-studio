#!/usr/bin/env python3
"""One screen answering "where is this project actually?" (development tooling).

The facts that decide what to work on next are spread across a git checkout, four
asset directories, thirty-eight QC records, a mouth anchor, and the PHASE 6 gate.
Reading them one at a time is how a phase gets declared ready while its gate still
reports eight problems. This collects them and prints them together.

It decides nothing. The gate is `lock_library.py`, the prompt check is
`compile_prompt.py --lint`, the code check is the test suite; this only reports what
they would say. So it exits 0 even when the project is in poor shape - a status
command that fails the build is a check wearing the wrong name.

Usage:
    status.py                 human-readable status
    status.py --json          the same facts as JSON
    status.py --verbose       every gate problem, not the first few
    status.py --no-gate       skip the PHASE 6 gate (git and file counts only)

Exit code 0 = report produced, 2 = usage error.
"""

import argparse
import contextlib
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "validation"))
import canon                                       # noqa: E402

REPO = Path(os.environ.get("NARRA_REPO", Path(__file__).resolve().parents[2]))

PROMPT_DIRS = {"expression": REPO / "prompts" / "expressions",
               "viseme": REPO / "prompts" / "visemes",
               "pose": REPO / "prompts" / "poses"}
MASTER_DIR = REPO / "prompts" / "master"
VALIDATION_DIR = REPO / "metadata" / "validation"
LOCK_FILE = REPO / "metadata" / "production-lock.json"
TIMELINE_DIR = REPO / "metadata" / "timelines"
ANIMATION_DIR = REPO / "metadata" / "animations"
FRAME_DIR = REPO / "assets" / "frames"

# prompts/README.md 3: <name>-v<major>.<minor>.md
PROMPT_RE = re.compile(r"^(?P<name>[a-z0-9-]+)-v(?P<version>\d+\.\d+)$")

SET_ORDER = ["expression", "viseme", "pose"]
GATE_PROBLEM_PREVIEW = 5


def git(*args):
    """A git query, or None outside a checkout / without git installed."""
    try:
        done = subprocess.run(("git", "-C", str(REPO)) + args,
                              capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.rstrip("\n") if done.returncode == 0 else None


def repository():
    head = git("log", "-1", "--format=%h %s")
    if head is None:
        return None
    porcelain = git("status", "--porcelain") or ""
    dirty = [line for line in porcelain.splitlines() if line.strip()]
    return {"branch": git("rev-parse", "--abbrev-ref", "HEAD") or "(detached)",
            "head": head,
            "dirty": len(dirty),
            "untracked": sum(1 for line in dirty if line.startswith("??"))}


def prompt_names(directory):
    """Canonical names covered by at least one prompt file in `directory`."""
    if not directory.is_dir():
        return set()
    names = set()
    for path in directory.glob("*.md"):
        match = PROMPT_RE.match(path.stem)
        if match:
            names.add(match.group("name").lower())
    return names


def prompts():
    state = {"master": sorted(p.name for p in MASTER_DIR.glob("*.md"))
             if MASTER_DIR.is_dir() else []}
    for asset_type in SET_ORDER:
        covered = prompt_names(PROMPT_DIRS[asset_type])
        expected = canon.CANONICAL[asset_type]
        state[asset_type] = {
            "present": sum(1 for name in expected if name.lower() in covered),
            "required": canon.REQUIRED_COUNTS[asset_type],
            "missing": [name for name in expected if name.lower() not in covered],
        }
    return state


def approvals():
    """QC sign-offs recorded by validate_asset.py --approve, by outcome."""
    tally = {"approved": 0, "pending": 0, "failed": 0}
    if not VALIDATION_DIR.is_dir():
        return tally
    for path in sorted(VALIDATION_DIR.glob("*.json")):
        try:
            overall = json.loads(path.read_text()).get("overall")
        except (OSError, json.JSONDecodeError):
            overall = None
        if overall == "approved":
            tally["approved"] += 1
        elif overall == "failed":
            tally["failed"] += 1
        else:
            tally["pending"] += 1
    return tally


def library(lock_library):
    """What is on disk in character/, before any question of whether it is good."""
    state = {}
    for asset_type in SET_ORDER:
        found, strays = lock_library.library_assets(asset_type)
        state[asset_type] = {
            "present": len(found),
            "required": canon.REQUIRED_COUNTS[asset_type],
            "missing": [name for name in canon.CANONICAL[asset_type] if name not in found],
            "strays": [path.name for path in strays],
        }
    state["approvals"] = approvals()
    state["total_required"] = sum(canon.REQUIRED_COUNTS[t] for t in SET_ORDER)
    return state


def gate(lock_library, imagecheck):
    """Run the PHASE 6 gate for its verdict only; lock_library.py prints the detail."""
    report = imagecheck.Report()
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            lock_library.run_gate(report)
        except Exception as error:                      # noqa: BLE001 - status must not die
            return {"ran": False, "error": f"{type(error).__name__}: {error}"}
    problems = [f"{name}: {detail}" for level, name, detail in report.rows
                if level == imagecheck.FAIL]
    return {"ran": True, "passed": not problems, "counts": report.counts(),
            "problems": problems}


def lock():
    if not LOCK_FILE.exists():
        return {"written": False}
    try:
        doc = json.loads(LOCK_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {"written": True, "readable": False}
    return {"written": True, "readable": True,
            "locked_at": doc.get("locked_at", ""), "locked_by": doc.get("locked_by", ""),
            "assets": len(doc.get("assets", []))}


def artefacts():
    """PHASE 7 and PHASE 8 output. Generated, gitignored, and cheap to count."""
    def count(directory, pattern):
        return len(list(directory.glob(pattern))) if directory.is_dir() else 0
    return {"timelines": count(TIMELINE_DIR, "*.json"),
            "animations": count(ANIMATION_DIR, "*.json"),
            "frame_sets": len([p for p in FRAME_DIR.iterdir() if p.is_dir()])
            if FRAME_DIR.is_dir() else 0}


def collect(run_gate=True):
    state = {"repo": str(REPO), "repository": repository(),
             "prompts": prompts(), "artefacts": artefacts(), "lock": lock()}
    import imagecheck                                   # noqa: E402
    import lock_library                                 # noqa: E402
    state["library"] = library(lock_library)
    state["gate"] = gate(lock_library, imagecheck) if run_gate else {"ran": False}
    return state


# --- rendering -------------------------------------------------------------


def row(label, value):
    return f"  {label.ljust(16)}{value}"


def ratio(entry):
    line = f"{entry['present']} / {entry['required']}"
    if entry.get("strays"):
        line += f"  ({len(entry['strays'])} stray: {', '.join(entry['strays'][:3])})"
    return line


def render(state, verbose=False):
    lines = ["", "NARRA - project status", ""]

    lines.append("Repository")
    repo = state["repository"]
    if repo is None:
        lines.append(row("git", "not a git checkout"))
    else:
        lines.append(row("branch", repo["branch"]))
        lines.append(row("head", repo["head"]))
        lines.append(row("working tree", "clean" if not repo["dirty"] else
                         f"{repo['dirty']} changed file(s), "
                         f"{repo['untracked']} untracked"))
    lines.append("")

    lines.append("Prompts")
    master = state["prompts"]["master"]
    lines.append(row("master", master[0] if master else "missing"))
    for asset_type in SET_ORDER:
        lines.append(row(f"{asset_type}s", ratio(state["prompts"][asset_type])))
    lines.append("")

    lines.append("Image library (PHASE 1-6)")
    for asset_type in SET_ORDER:
        lines.append(row(f"{asset_type}s", ratio(state["library"][asset_type])))
    tally = state["library"]["approvals"]
    lines.append(row("QC sign-offs", f"{tally['approved']} approved / "
                     f"{state['library']['total_required']} required"
                     + (f", {tally['pending']} pending" if tally["pending"] else "")
                     + (f", {tally['failed']} failed" if tally["failed"] else "")))
    lines.append("")

    lines.append("PHASE 6 gate")
    gate_state = state["gate"]
    if not gate_state.get("ran"):
        lines.append(row("result", gate_state.get("error", "not run")))
    elif gate_state["passed"]:
        lines.append(row("result", "PASS"))
    else:
        problems = gate_state["problems"]
        shown = problems if verbose else problems[:GATE_PROBLEM_PREVIEW]
        lines.append(row("result", f"FAIL - {len(problems)} blocking problem(s)"))
        lines.extend(f"    - {problem}" for problem in shown)
        if len(shown) < len(problems):
            lines.append(f"    ... {len(problems) - len(shown)} more; "
                         f"run scripts/validation/lock_library.py, or status.py --verbose")
    lock_state = state["lock"]
    if not lock_state["written"]:
        lines.append(row("production lock", "not written"))
    elif not lock_state.get("readable"):
        lines.append(row("production lock", "present but not valid JSON"))
    else:
        lines.append(row("production lock", f"{lock_state['assets']} asset(s), locked by "
                         f"{lock_state['locked_by'] or '(unrecorded)'} "
                         f"{lock_state['locked_at']}"))
    lines.append("")

    lines.append("Generated artefacts (PHASE 7-8)")
    art = state["artefacts"]
    lines.append(row("timelines", art["timelines"]))
    lines.append(row("animations", art["animations"]))
    lines.append(row("frame sets", art["frame_sets"]))
    lines.append("")

    lines.append("Next")
    lines.extend(f"  {line}" for line in next_steps(state))
    lines.append("")
    return "\n".join(lines)


def next_steps(state):
    """The one or two things this state is asking for. Not a plan - a pointer."""
    gate_state = state["gate"]
    if not gate_state.get("ran"):
        return ["gate not run - scripts/validation/lock_library.py"]
    if not gate_state["passed"]:
        missing = sum(len(state["library"][t]["missing"]) for t in SET_ORDER)
        steps = ["PHASE 6 gate fails, so PHASE 9 stays blocked (CLAUDE.md phase gate)."]
        if missing:
            steps.append(f"{missing} of {state['library']['total_required']} image assets "
                         "do not exist yet - PHASE 1-5 generation is the work.")
        steps.append("Detail: python3 scripts/validation/lock_library.py")
        return steps
    if not state["lock"]["written"]:
        return ["gate passes and the lock is unwritten - "
                "lock_library.py --lock --by \"name\""]
    return ["gate passes and the library is locked; PHASE 9 is unblocked."]


def main():
    parser = argparse.ArgumentParser(
        description="Report project status: git, prompts, image library, PHASE 6 gate.")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="emit the collected facts as JSON")
    parser.add_argument("--verbose", action="store_true",
                        help="list every gate problem, not the first few")
    parser.add_argument("--no-gate", action="store_false", dest="run_gate",
                        help="skip the PHASE 6 gate")
    args = parser.parse_args()

    state = collect(run_gate=args.run_gate)
    if args.as_json:
        print(json.dumps(state, indent=2))
    else:
        print(render(state, verbose=args.verbose))
    return 0


if __name__ == "__main__":
    sys.exit(main())
