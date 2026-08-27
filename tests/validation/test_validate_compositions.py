#!/usr/bin/env python3
"""Tests for scripts/validation/validate_compositions.py (PHASE 5.3).

The rule under test is the one that is easy to get wrong and expensive to discover
later: an open-mouth expression cannot host a viseme track.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "validation" / "validate_compositions.py"

sys.path.insert(0, str(REPO / "scripts" / "lib"))
import canon  # noqa: E402

POSE_CLASSES = {
    "neutral": "medium", "explaining": "medium", "surprised": "medium",
    "thinking": "medium", "concerned": "medium", "pointing-left": "upper-body",
    "pointing-right": "upper-body", "presenting": "upper-body",
    "excited": "upper-body", "confident": "three-quarter",
}


def state(pose="neutral", expression="neutral", camera_class="medium",
          mouth="viseme-track", idle="REST", **overrides):
    data = {
        "description": "A state.",
        "pose": pose,
        "camera_class": camera_class,
        "expression": expression,
        "mouth": mouth,
        "idle_viseme": idle,
    }
    data.update(overrides)
    return data


class ValidateCompositionsTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        poses = self.repo / "prompts" / "poses"
        poses.mkdir(parents=True)
        for name, camera_class in POSE_CLASSES.items():
            (poses / f"{name}-v1.0.md").write_text(
                f"---\nid: {name}\nversion: 1.0\nkind: pose\nasset_name: {name}\n"
                f"camera_class: {camera_class}\ntask_target: the body\n---\n\n"
                "## TASK\n\nChange only the body.\n")
        self.states_file = self.repo / "character" / "compositions" / "narrator-states.json"
        self.states_file.parent.mkdir(parents=True)
        self.addCleanup(self._tmp.cleanup)

    def write(self, states, character="narra"):
        self.states_file.write_text(json.dumps(
            {"character": character, "version": 1, "states": states}, indent=2))

    def valid_states(self):
        return {
            "talking": state(),
            "explaining": state(pose="explaining", expression="friendly"),
            "presenting": state(pose="presenting", expression="happy",
                                camera_class="upper-body"),
            "reaction": state(pose="surprised", expression="surprised",
                              mouth="static", idle=None),
            "emphasis": state(pose="excited", expression="excited",
                              camera_class="upper-body", mouth="static", idle=None),
        }

    def run_cli(self, *args):
        env = dict(os.environ, NARRA_REPO=str(self.repo))
        return subprocess.run([sys.executable, str(SCRIPT), *[str(a) for a in args]],
                              capture_output=True, text=True, env=env)

    # --- happy path ------------------------------------------------------

    def test_valid_compositions_pass(self):
        self.write(self.valid_states())
        result = self.run_cli(self.states_file)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("5 composition(s) valid", result.stdout)

    # --- the layering rule -----------------------------------------------

    def test_viseme_track_over_an_open_mouth_expression_fails(self):
        states = self.valid_states()
        states["explaining"] = state(pose="explaining", expression="explaining")
        self.write(states)
        result = self.run_cli(self.states_file)
        self.assertEqual(result.returncode, 1)
        self.assertIn("already carries an open mouth", result.stdout)
        self.assertIn("two mouths", result.stdout)

    def test_every_open_mouth_expression_is_rejected_with_a_viseme_track(self):
        for expression in canon.OPEN_MOUTH_EXPRESSIONS:
            with self.subTest(expression=expression):
                states = self.valid_states()
                states["talking"] = state(expression=expression)
                self.write(states)
                self.assertEqual(self.run_cli(self.states_file).returncode, 1)

    def test_static_mouth_over_an_open_mouth_expression_is_fine(self):
        states = self.valid_states()
        states["reaction"] = state(pose="surprised", expression="surprised",
                                   mouth="static", idle=None)
        self.write(states)
        self.assertEqual(self.run_cli(self.states_file).returncode, 0)

    def test_viseme_track_without_an_idle_viseme_fails(self):
        states = self.valid_states()
        states["talking"] = state(idle=None)
        self.write(states)
        result = self.run_cli(self.states_file)
        self.assertEqual(result.returncode, 1)
        self.assertIn("idle_viseme", result.stdout)

    def test_non_canonical_idle_viseme_fails(self):
        states = self.valid_states()
        states["talking"] = state(idle="HUM")
        self.write(states)
        self.assertEqual(self.run_cli(self.states_file).returncode, 1)

    def test_idle_viseme_on_a_static_state_warns(self):
        states = self.valid_states()
        states["reaction"] = state(pose="surprised", expression="surprised",
                                   mouth="static", idle="REST")
        self.write(states)
        result = self.run_cli(self.states_file)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("[WARN]", result.stdout)
        self.assertIn("will be ignored", result.stdout)

    # --- canonical references --------------------------------------------

    def test_required_states_must_all_be_present(self):
        states = self.valid_states()
        del states["emphasis"]
        self.write(states)
        result = self.run_cli(self.states_file)
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing: emphasis", result.stdout)

    def test_non_canonical_pose_fails(self):
        states = self.valid_states()
        states["talking"] = state(pose="lounging")
        self.write(states)
        result = self.run_cli(self.states_file)
        self.assertEqual(result.returncode, 1)
        self.assertIn("canonical pose set", result.stdout)

    def test_non_canonical_expression_fails(self):
        states = self.valid_states()
        states["talking"] = state(expression="smug")
        self.write(states)
        result = self.run_cli(self.states_file)
        self.assertEqual(result.returncode, 1)
        self.assertIn("canonical expression set", result.stdout)

    def test_camera_class_disagreeing_with_the_pose_prompt_fails(self):
        states = self.valid_states()
        states["talking"] = state(camera_class="three-quarter")
        self.write(states)
        result = self.run_cli(self.states_file)
        self.assertEqual(result.returncode, 1)
        self.assertIn("disagree", result.stdout)

    def test_unknown_camera_class_fails(self):
        states = self.valid_states()
        states["talking"] = state(camera_class="extreme-close-up")
        self.write(states)
        self.assertEqual(self.run_cli(self.states_file).returncode, 1)

    def test_unknown_mouth_mode_fails(self):
        states = self.valid_states()
        states["talking"] = state(mouth="lipsync")
        self.write(states)
        self.assertEqual(self.run_cli(self.states_file).returncode, 1)

    def test_missing_required_field_fails(self):
        states = self.valid_states()
        del states["talking"]["description"]
        self.write(states)
        self.assertEqual(self.run_cli(self.states_file).returncode, 1)

    def test_wrong_character_fails(self):
        self.write(self.valid_states(), character="someone-else")
        self.assertEqual(self.run_cli(self.states_file).returncode, 1)

    # --- file handling ---------------------------------------------------

    def test_extra_states_beyond_the_required_five_are_allowed(self):
        states = self.valid_states()
        states["listening"] = state(pose="thinking", expression="serious")
        self.write(states)
        result = self.run_cli(self.states_file)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("6 composition(s) valid", result.stdout)

    def test_invalid_json_fails(self):
        self.states_file.write_text("{ not json")
        self.assertEqual(self.run_cli(self.states_file).returncode, 1)

    def test_empty_states_fails(self):
        self.write({})
        self.assertEqual(self.run_cli(self.states_file).returncode, 1)

    def test_missing_file_is_a_usage_error(self):
        self.assertEqual(self.run_cli(self.repo / "nope.json").returncode, 2)


class RealCompositionsTest(unittest.TestCase):
    """The file that actually ships."""

    def test_shipped_compositions_validate(self):
        result = subprocess.run([sys.executable, str(SCRIPT)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_every_required_state_is_defined(self):
        data = json.loads(
            (REPO / "character" / "compositions" / "narrator-states.json").read_text())
        for name in canon.NARRATOR_STATES:
            self.assertIn(name, data["states"])


if __name__ == "__main__":
    unittest.main()
