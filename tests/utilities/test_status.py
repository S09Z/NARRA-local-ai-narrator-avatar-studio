#!/usr/bin/env python3
"""Tests for scripts/utilities/status.py (development tooling).

Status reports; it does not judge. The contracts worth pinning are that it counts
the right things, that it survives a repository in any state, and above all that a
failing project still exits 0 - the moment `make status` can fail a build, someone
starts working around it.

Run:
    python3 -m unittest discover -s tests -p 'test_*.py' -v
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "utilities" / "status.py"

sys.path.insert(0, str(REPO / "scripts" / "lib"))
import canon                                          # noqa: E402

SUBDIR = {"expression": "expressions", "viseme": "visemes", "pose": "poses"}


class StatusTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        for part in ("prompts/master", "prompts/expressions", "prompts/visemes",
                     "prompts/poses", "character/reference", "character/expressions",
                     "character/visemes", "character/poses", "metadata/validation",
                     "metadata/timelines", "metadata/animations", "assets/frames"):
            (self.repo / part).mkdir(parents=True)
        self.addCleanup(self._tmp.cleanup)

    # --- helpers ----------------------------------------------------------

    def status(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              capture_output=True, text=True,
                              env=dict(os.environ, NARRA_REPO=str(self.repo)))

    def state(self, *args):
        result = self.status("--json", *args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def add_prompt(self, asset_type, name, version="1.0"):
        path = (self.repo / "prompts" / SUBDIR[asset_type]
                / f"{name.lower()}-v{version}.md")
        path.write_text("# prompt\n")
        return path

    def add_asset(self, asset_type, name, version=1):
        path = (self.repo / "character" / SUBDIR[asset_type]
                / canon.asset_filename(asset_type, name, version))
        path.write_bytes(b"")
        return path

    def add_review(self, asset_type, name, overall="approved", version=1):
        stem = canon.asset_filename(asset_type, name, version).removesuffix(".png")
        (self.repo / "metadata" / "validation" / f"{stem}.json").write_text(
            json.dumps({"overall": overall}))

    # --- the contract that matters ----------------------------------------

    def test_exits_zero_although_the_gate_fails(self):
        result = self.status()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("FAIL", result.stdout)

    def test_reports_the_gate_verdict_and_problem_count(self):
        gate = self.state()["gate"]
        self.assertTrue(gate["ran"])
        self.assertFalse(gate["passed"])
        self.assertTrue(any("reference" in problem for problem in gate["problems"]))

    def test_no_gate_skips_the_gate(self):
        state = self.state("--no-gate")
        self.assertFalse(state["gate"]["ran"])
        self.assertEqual(state["library"]["expression"]["required"], 12)

    def test_verbose_lists_every_problem(self):
        problems = len(self.state()["gate"]["problems"])
        brief = self.status().stdout
        full = self.status("--verbose").stdout
        self.assertIn("more;", brief)
        self.assertNotIn("more;", full)
        self.assertEqual(full.count("\n    - "), problems)

    # --- counting ---------------------------------------------------------

    def test_counts_prompts_against_the_canonical_sets(self):
        for name in canon.VISEMES:
            self.add_prompt("viseme", name)
        self.add_prompt("expression", "friendly")
        state = self.state("--no-gate")["prompts"]
        self.assertEqual(state["viseme"]["present"], 16)
        self.assertEqual(state["viseme"]["missing"], [])
        self.assertEqual(state["expression"]["present"], 1)
        self.assertIn("neutral", state["expression"]["missing"])

    def test_ignores_prompt_files_that_are_not_versioned_assets(self):
        (self.repo / "prompts" / "visemes" / "README.md").write_text("notes\n")
        (self.repo / "prompts" / "visemes" / "mbp.md").write_text("unversioned\n")
        self.assertEqual(self.state("--no-gate")["prompts"]["viseme"]["present"], 0)

    def test_reports_the_master_prompt(self):
        self.assertEqual(self.state("--no-gate")["prompts"]["master"], [])
        (self.repo / "prompts" / "master" / "master-character-v1.0.md").write_text("x\n")
        self.assertEqual(self.state("--no-gate")["prompts"]["master"],
                         ["master-character-v1.0.md"])

    def test_counts_library_assets_and_names_strays(self):
        self.add_asset("pose", "neutral")
        (self.repo / "character" / "poses" / "narra-pose-jazzhands-v1.png").write_bytes(b"")
        state = self.state("--no-gate")["library"]["pose"]
        self.assertEqual(state["present"], 1)
        self.assertEqual(state["required"], 10)
        self.assertNotIn("neutral", state["missing"])
        self.assertEqual(state["strays"], ["narra-pose-jazzhands-v1.png"])

    def test_tallies_qc_sign_offs_by_outcome(self):
        self.add_review("expression", "neutral", "approved")
        self.add_review("expression", "friendly", "pending-human-review")
        self.add_review("expression", "happy", "failed")
        tally = self.state("--no-gate")["library"]["approvals"]
        self.assertEqual(tally, {"approved": 1, "pending": 1, "failed": 1})
        self.assertEqual(self.state("--no-gate")["library"]["total_required"], 38)

    def test_unreadable_review_counts_as_pending_not_approved(self):
        (self.repo / "metadata" / "validation" / "broken.json").write_text("{not json")
        tally = self.state("--no-gate")["library"]["approvals"]
        self.assertEqual(tally["approved"], 0)
        self.assertEqual(tally["pending"], 1)

    def test_counts_generated_artefacts(self):
        (self.repo / "metadata" / "timelines" / "a.json").write_text("{}")
        (self.repo / "metadata" / "animations" / "a.json").write_text("{}")
        (self.repo / "assets" / "frames" / "clip-a").mkdir()
        self.assertEqual(self.state("--no-gate")["artefacts"],
                         {"timelines": 1, "animations": 1, "frame_sets": 1})

    def test_reports_the_production_lock_when_written(self):
        self.assertFalse(self.state("--no-gate")["lock"]["written"])
        (self.repo / "metadata" / "production-lock.json").write_text(json.dumps(
            {"locked_at": "2026-08-28T00:00:00+00:00", "locked_by": "tester",
             "assets": [{"name": "neutral"}]}))
        lock = self.state("--no-gate")["lock"]
        self.assertEqual((lock["locked_by"], lock["assets"]), ("tester", 1))

    # --- survives an unusual tree -----------------------------------------

    def test_survives_a_tree_with_no_git_and_no_directories(self):
        bare = Path(self._tmp.name) / "bare"
        bare.mkdir()
        result = subprocess.run([sys.executable, str(SCRIPT)],
                                capture_output=True, text=True,
                                env=dict(os.environ, NARRA_REPO=str(bare)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("not a git checkout", result.stdout)

    def test_rejects_an_unknown_flag(self):
        self.assertEqual(self.status("--lock").returncode, 2)


class NextStepsTest(unittest.TestCase):
    """The pointer line, unit-tested - a passing gate is not buildable in a temp dir."""

    def setUp(self):
        sys.path.insert(0, str(REPO / "scripts" / "utilities"))
        import status
        self.status = status

    def state(self, **gate):
        library = {t: {"missing": []} for t in ("expression", "viseme", "pose")}
        library["total_required"] = 38
        return {"gate": gate, "library": library, "lock": {"written": False}}

    def test_failing_gate_points_at_the_gate(self):
        state = self.state(ran=True, passed=False)
        state["library"]["viseme"]["missing"] = ["MBP"]
        steps = " ".join(self.status.next_steps(state))
        self.assertIn("PHASE 9 stays blocked", steps)
        self.assertIn("1 of 38 image assets", steps)

    def test_passing_gate_without_a_lock_points_at_the_lock(self):
        steps = " ".join(self.status.next_steps(self.state(ran=True, passed=True)))
        self.assertIn("--lock --by", steps)

    def test_passing_gate_with_a_lock_reports_phase_9_unblocked(self):
        state = self.state(ran=True, passed=True)
        state["lock"] = {"written": True, "readable": True, "assets": 38}
        steps = " ".join(self.status.next_steps(state))
        self.assertIn("PHASE 9 is unblocked", steps)

    def test_skipped_gate_says_so(self):
        steps = " ".join(self.status.next_steps(self.state(ran=False)))
        self.assertIn("gate not run", steps)


if __name__ == "__main__":
    unittest.main()
