#!/usr/bin/env python3
"""Pins the real PHASE 3 expression prompt set in prompts/expressions/.

Unlike test_compile_prompt.py, which uses throwaway fixtures, this checks the
files that will actually generate the library.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COMPILE = REPO / "scripts" / "generation" / "compile_prompt.py"
EXPRESSION_DIR = REPO / "prompts" / "expressions"

sys.path.insert(0, str(REPO / "scripts" / "lib"))
import canon  # noqa: E402

# ASSET_SPEC.md section 6 - the only three expressions defined by an open mouth.
OPEN_MOUTH = {"excited", "surprised", "explaining"}


def compile_expression(name):
    result = subprocess.run(
        [sys.executable, str(COMPILE), f"expressions/{name}-v1.0.md", "--json"],
        capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError(f"{name} failed to compile: {result.stderr}")
    return json.loads(result.stdout)


class ExpressionSetTest(unittest.TestCase):

    def test_every_canonical_expression_has_a_prompt(self):
        for name in canon.EXPRESSIONS:
            with self.subTest(expression=name):
                self.assertTrue((EXPRESSION_DIR / f"{name}-v1.0.md").exists())

    def test_there_are_no_extra_prompt_files(self):
        stems = {path.stem.rsplit("-v", 1)[0] for path in EXPRESSION_DIR.glob("*.md")}
        self.assertEqual(stems, set(canon.EXPRESSIONS))

    def test_seeds_are_the_canonical_index(self):
        for index, name in enumerate(canon.EXPRESSIONS):
            with self.subTest(expression=name):
                self.assertEqual(compile_expression(name)["seed"], 10000 + index)

    def test_rest_mouth_expressions_preserve_the_mouth(self):
        for name in set(canon.EXPRESSIONS) - OPEN_MOUTH:
            with self.subTest(expression=name):
                compiled = compile_expression(name)["compiled"]
                kept = [line for line in compiled.splitlines()
                        if "Keep the same person" in line][0]
                self.assertIn("mouth shape and position", kept,
                              f"{name} must carry a REST mouth so visemes composite "
                              "(ASSET_SPEC 6)")

    def test_open_mouth_expressions_release_the_mouth(self):
        for name in OPEN_MOUTH:
            with self.subTest(expression=name):
                compiled = compile_expression(name)["compiled"]
                kept = [line for line in compiled.splitlines()
                        if "Keep the same person" in line][0]
                self.assertNotIn("mouth shape and position", kept)

    def test_no_expression_carries_a_viseme_block(self):
        for name in canon.EXPRESSIONS:
            with self.subTest(expression=name):
                self.assertNotIn("VISEME:", compile_expression(name)["compiled"])

    def test_every_expression_states_an_intensity(self):
        for name in canon.EXPRESSIONS:
            with self.subTest(expression=name):
                text = (EXPRESSION_DIR / f"{name}-v1.0.md").read_text()
                self.assertIn("Intensity:", text)

    def test_expression_bodies_are_distinct(self):
        bodies = {}
        for name in canon.EXPRESSIONS:
            compiled = compile_expression(name)["compiled"]
            block = [c for c in compiled.split("\n\n") if c.startswith("EXPRESSION:")][0]
            self.assertNotIn(block, bodies,
                             f"{name} has the same EXPRESSION block as {bodies.get(block)}")
            bodies[block] = name


if __name__ == "__main__":
    unittest.main()
