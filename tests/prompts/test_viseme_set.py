#!/usr/bin/env python3
"""Pins the real PHASE 4 viseme prompt set in prompts/visemes/."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COMPILE = REPO / "scripts" / "generation" / "compile_prompt.py"
VISEME_DIR = REPO / "prompts" / "visemes"

sys.path.insert(0, str(REPO / "scripts" / "lib"))
import canon  # noqa: E402

# PROMPT_GUIDE.md section 6 descriptor template.
DESCRIPTORS = ["jaw:", "lips:", "opening:", "width:", "teeth:", "tongue:"]


def compile_viseme(name):
    result = subprocess.run(
        [sys.executable, str(COMPILE), f"visemes/{name.lower()}-v1.0.md", "--json"],
        capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError(f"{name} failed to compile: {result.stderr}")
    return json.loads(result.stdout)


class VisemeSetTest(unittest.TestCase):

    def test_every_canonical_viseme_has_a_prompt(self):
        for name in canon.VISEMES:
            with self.subTest(viseme=name):
                self.assertTrue((VISEME_DIR / f"{name.lower()}-v1.0.md").exists())

    def test_there_are_no_extra_prompt_files(self):
        stems = {path.stem.rsplit("-v", 1)[0] for path in VISEME_DIR.glob("*.md")}
        self.assertEqual(stems, {name.lower() for name in canon.VISEMES})

    def test_seeds_are_the_canonical_index(self):
        for index, name in enumerate(canon.VISEMES):
            with self.subTest(viseme=name):
                self.assertEqual(compile_viseme(name)["seed"], 20000 + index)

    def test_mbp_seed_matches_the_asset_spec_example(self):
        self.assertEqual(compile_viseme("MBP")["seed"], 20008)

    def test_names_are_recorded_uppercase(self):
        for name in canon.VISEMES:
            with self.subTest(viseme=name):
                self.assertEqual(compile_viseme(name)["asset_name"], name)

    def test_every_task_says_change_only_the_mouth(self):
        # PLAN.md section 4.4 states this verbatim as a requirement.
        for name in canon.VISEMES:
            with self.subTest(viseme=name):
                compiled = compile_viseme(name)["compiled"]
                task = [c for c in compiled.split("\n\n") if c.startswith("TASK:")][0]
                self.assertIn("Change only the mouth", task)

    def test_no_viseme_carries_an_expression_block(self):
        for name in canon.VISEMES:
            with self.subTest(viseme=name):
                self.assertNotIn("EXPRESSION:", compile_viseme(name)["compiled"])

    def test_every_viseme_preserves_everything_but_the_mouth(self):
        for name in canon.VISEMES:
            with self.subTest(viseme=name):
                compiled = compile_viseme(name)["compiled"]
                kept = [line for line in compiled.splitlines()
                        if "Keep the same person" in line][0]
                self.assertNotIn("mouth shape and position", kept)
                for feature in ("eye shape and position", "eyebrows", "hairstyle",
                                "camera framing"):
                    self.assertIn(feature, kept)

    def test_mouth_position_negative_is_retained(self):
        # The mouth SHAPE changes; the mouth POSITION must not (ASSET_SPEC 9).
        for name in canon.VISEMES:
            with self.subTest(viseme=name):
                self.assertIn("moved mouth position", compile_viseme(name)["negative"])

    def test_every_viseme_uses_the_full_descriptor_template(self):
        for name in canon.VISEMES:
            with self.subTest(viseme=name):
                compiled = compile_viseme(name)["compiled"]
                block = [c for c in compiled.split("\n\n") if c.startswith("VISEME:")][0]
                for descriptor in DESCRIPTORS:
                    self.assertIn(descriptor, block,
                                  f"{name} is missing '{descriptor}' (PROMPT_GUIDE.md 6)")

    def test_viseme_bodies_are_distinct(self):
        bodies = {}
        for name in canon.VISEMES:
            block = [c for c in compile_viseme(name)["compiled"].split("\n\n")
                     if c.startswith("VISEME:")][0]
            self.assertNotIn(block, bodies,
                             f"{name} has the same VISEME block as {bodies.get(block)}")
            bodies[block] = name

    def test_mbp_and_rest_differ_in_lip_tension(self):
        # ASSET_SPEC 7: these two must be distinguishable, and both fail if not.
        rest = (VISEME_DIR / "rest-v1.0.md").read_text()
        mbp = (VISEME_DIR / "mbp-v1.0.md").read_text()
        self.assertIn("relaxed", rest)
        self.assertIn("no muscular tension", rest)
        self.assertIn("actively pressed", mbp)
        self.assertIn("compression", mbp)


class ThaiMappingTest(unittest.TestCase):

    MAPPING = REPO / "docs" / "thai-viseme" / "thai-viseme-mapping.md"

    def test_mapping_document_exists(self):
        self.assertTrue(self.MAPPING.exists())

    def test_every_viseme_appears_in_the_mapping(self):
        text = self.MAPPING.read_text()
        for name in canon.VISEMES:
            with self.subTest(viseme=name):
                self.assertIn(f"`{name}`", text)

    def test_mapping_states_it_is_unreviewed(self):
        # The claim that this is an approximation, not an authority, must survive edits.
        text = self.MAPPING.read_text()
        self.assertIn("has not been reviewed by a Thai speaker", text)


if __name__ == "__main__":
    unittest.main()
