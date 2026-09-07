#!/usr/bin/env python3
"""Tests for scripts/utilities/demo_run.py (development tooling).

Two contracts carry the weight. The walkthrough must write nothing - a first run
that quietly creates files is a first run nobody can trust on a real library. And it
must exit 0 on a project in any state, including an empty one, because the moment
`make demo` can fail a build someone starts routing around it.

Run:
    python3 -m unittest discover -s tests -p 'test_*.py' -v
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "utilities" / "demo_run.py"

sys.path.insert(0, str(REPO / "scripts" / "utilities"))
import demo_run                                       # noqa: E402

MEASURED_ANCHOR = {
    "character": "narra",
    "status": "measured",
    "anchor": {"anchor_x": 0.5, "anchor_y": 0.62,
               "mouth_width": 0.14, "mouth_height": 0.05},
}


class DemoRunTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        for part in ("prompts/master", "prompts/expressions", "prompts/visemes",
                     "prompts/poses", "character/reference", "character/bible",
                     "character/expressions", "character/visemes", "character/poses",
                     "metadata/validation"):
            (self.repo / part).mkdir(parents=True)
        self.addCleanup(self._tmp.cleanup)

    # --- helpers ----------------------------------------------------------

    def demo(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              capture_output=True, text=True,
                              env=dict(os.environ, NARRA_REPO=str(self.repo)))

    def steps(self, *args):
        result = self.demo("--json", *args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return {step["key"]: step for step in json.loads(result.stdout)["steps"]}

    def add_bible(self, character_tbd=0, spec_tbd=0):
        bible = self.repo / "character" / "bible"
        (bible / "character-bible.md").write_text("# bible\n" + "TBD\n" * character_tbd)
        (bible / "visual-spec.md").write_text("# spec\n" + "TBD\n" * spec_tbd)

    def add_anchor(self, doc):
        (self.repo / "character" / "bible" / "mouth-anchor.json").write_text(
            json.dumps(doc))

    def tree(self):
        """Every file under the sandbox, by content."""
        return {str(path.relative_to(self.repo)):
                hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(self.repo.rglob("*")) if path.is_file()}

    # --- the two load-bearing contracts -----------------------------------

    def test_empty_project_still_exits_zero(self):
        result = self.demo()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("NARRA - demo first run", result.stdout)

    def test_writes_nothing(self):
        self.add_bible(character_tbd=3)
        self.add_anchor(MEASURED_ANCHOR)
        before = self.tree()
        self.demo()
        self.assertEqual(self.tree(), before)

    # --- reporting --------------------------------------------------------

    def test_reports_every_step(self):
        self.assertEqual(set(self.steps()), {key for key, *_ in demo_run.STEPS})

    def test_every_step_carries_a_state(self):
        for key, step in self.steps().items():
            with self.subTest(step=key):
                self.assertIn(step["state"], (demo_run.OK, demo_run.TODO, demo_run.BLOCKED))

    def test_next_action_names_a_step(self):
        result = self.demo("--json")
        self.assertRegex(json.loads(result.stdout)["next"], r"^(step \d+|nothing)")

    # --- step selection ---------------------------------------------------

    def test_list_names_every_step(self):
        result = self.demo("--list")
        self.assertEqual(result.returncode, 0)
        for key, *_ in demo_run.STEPS:
            self.assertIn(key, result.stdout)

    def test_step_runs_only_that_step(self):
        self.assertEqual(set(self.steps("--step", "bible")), {"bible"})

    def test_unknown_step_is_a_usage_error(self):
        result = self.demo("--step", "not-a-step")
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown step", result.stderr)

    # --- individual checks ------------------------------------------------

    def test_bible_counts_unfilled_fields(self):
        self.add_bible(character_tbd=4, spec_tbd=3)
        step = self.steps("--step", "bible")["bible"]
        self.assertEqual(step["state"], demo_run.TODO)
        self.assertIn("7", step["summary"])

    def test_bible_passes_when_filled(self):
        self.add_bible()
        self.assertEqual(self.steps("--step", "bible")["bible"]["state"], demo_run.OK)

    def test_bible_reports_missing_files(self):
        step = self.steps("--step", "bible")["bible"]
        self.assertEqual(step["state"], demo_run.TODO)
        self.assertIn("character-bible.md", step["summary"])

    def test_anchor_passes_when_measured(self):
        self.add_anchor(MEASURED_ANCHOR)
        self.assertEqual(self.steps("--step", "anchor")["anchor"]["state"], demo_run.OK)

    def test_anchor_todo_when_unmeasured(self):
        self.add_anchor(dict(MEASURED_ANCHOR, status="unmeasured",
                             anchor={"anchor_x": None, "anchor_y": None,
                                     "mouth_width": None, "mouth_height": None}))
        self.assertEqual(self.steps("--step", "anchor")["anchor"]["state"], demo_run.TODO)

    def test_anchor_survives_unreadable_json(self):
        (self.repo / "character" / "bible" / "mouth-anchor.json").write_text("{not json")
        self.assertEqual(self.steps("--step", "anchor")["anchor"]["state"], demo_run.TODO)

    def test_reference_todo_without_an_imported_reference(self):
        step = self.steps("--step", "reference")["reference"]
        self.assertEqual(step["state"], demo_run.TODO)
        self.assertIn("--import", "\n".join(step["detail"]))

    def test_generation_is_blocked_with_no_assets(self):
        self.assertEqual(self.steps("--step", "generate")["generate"]["state"],
                         demo_run.BLOCKED)

    def test_gate_is_blocked_with_no_assets(self):
        self.assertEqual(self.steps("--step", "gate")["gate"]["state"], demo_run.BLOCKED)

    # --- output -----------------------------------------------------------

    def test_verbose_includes_command_output(self):
        plain = self.demo("--step", "gate").stdout
        verbose = self.demo("--step", "gate", "--verbose").stdout
        self.assertNotIn("output", plain)
        self.assertIn("output", verbose)


if __name__ == "__main__":
    unittest.main()
