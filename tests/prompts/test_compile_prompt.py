#!/usr/bin/env python3
"""Tests for scripts/generation/compile_prompt.py (PHASE 2.2-2.4).

The compiler decides the exact text sent to FLUX for every asset in the library,
so its ordering, preservation, negative-filtering, and seed rules are pinned here.

Run:
    python3 -m unittest discover -s tests -p 'test_*.py' -v
"""

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "generation" / "compile_prompt.py"

MASTER = """\
---
id: master-character
version: 1.0
kind: master
---

## CHARACTER

A Thai narrator, early thirties, slim build.
hair: short black bob, center part

## STYLE

Flat 2D vector illustration, clean uniform outline.

## LIGHTING

Soft key from front-left, gentle fill.

## CAMERA

Close-up, front-facing, shoulders square.

## OUTPUT

1024x1024, square, flat uniform background.
"""

VISEME_MBP = """\
---
id: mbp
version: 1.0
kind: viseme
asset_name: MBP
task_target: the mouth and jaw
---

## TASK

Change only the mouth and jaw. Everything else is identical.

## VISEME

jaw: closed
lips: actively pressed together
"""


class CompilePromptTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        for sub in ("master", "expressions", "visemes", "poses", "diagnostic"):
            (self.repo / "prompts" / sub).mkdir(parents=True)
        self.write("master/master-character-v1.0.md", MASTER)
        self.addCleanup(self._tmp.cleanup)

    def write(self, relative, content):
        path = self.repo / "prompts" / relative
        path.write_text(textwrap.dedent(content))
        return path

    def run_cli(self, *args):
        env = dict(os.environ, NARRA_REPO=str(self.repo))
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              capture_output=True, text=True, env=env)

    def compile_json(self, relative):
        result = self.run_cli(relative, "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def blocks_in_order(self, compiled):
        return [chunk.split(":", 1)[0] for chunk in compiled.split("\n\n")]

    # --- block assembly --------------------------------------------------

    def test_blocks_emitted_in_prompt_guide_order(self):
        self.write("visemes/mbp-v1.0.md", VISEME_MBP)
        compiled = self.compile_json("visemes/mbp-v1.0.md")["compiled"]
        self.assertEqual(
            self.blocks_in_order(compiled),
            ["CHARACTER", "PRESERVATION", "TASK", "VISEME", "CAMERA", "LIGHTING",
             "STYLE", "OUTPUT"])

    def test_identity_precedes_task(self):
        self.write("visemes/mbp-v1.0.md", VISEME_MBP)
        compiled = self.compile_json("visemes/mbp-v1.0.md")["compiled"]
        self.assertLess(compiled.index("CHARACTER:"), compiled.index("TASK:"))
        self.assertLess(compiled.index("PRESERVATION:"), compiled.index("TASK:"))

    def test_master_content_is_included(self):
        self.write("visemes/mbp-v1.0.md", VISEME_MBP)
        compiled = self.compile_json("visemes/mbp-v1.0.md")["compiled"]
        self.assertIn("A Thai narrator, early thirties", compiled)
        self.assertIn("Flat 2D vector illustration", compiled)

    def test_asset_block_overrides_master_block(self):
        self.write("poses/presenting-v1.0.md", """\
            ---
            id: presenting
            version: 1.0
            kind: pose
            asset_name: presenting
            camera_class: upper-body
            task_target: the body, arms, and camera framing
            ---

            ## TASK

            Change only the body and arms. The face is identical.

            ## CAMERA

            Upper-body framing, camera pulled back.
            """)
        compiled = self.compile_json("poses/presenting-v1.0.md")["compiled"]
        self.assertIn("Upper-body framing, camera pulled back.", compiled)
        self.assertNotIn("Close-up, front-facing", compiled)

    def test_absent_blocks_are_omitted_not_blank(self):
        self.write("visemes/mbp-v1.0.md", VISEME_MBP)
        compiled = self.compile_json("visemes/mbp-v1.0.md")["compiled"]
        self.assertNotIn("EXPRESSION:", compiled)
        self.assertNotIn("POSE:", compiled)

    # --- preservation ----------------------------------------------------

    def test_preservation_omits_the_touched_feature(self):
        self.write("visemes/mbp-v1.0.md", VISEME_MBP)
        compiled = self.compile_json("visemes/mbp-v1.0.md")["compiled"]
        preservation = [c for c in compiled.split("\n\n") if c.startswith("PRESERVATION")][0]
        self.assertNotIn("mouth shape and position", preservation)
        self.assertIn("eye shape and position", preservation)
        self.assertIn("Do not change anything except the mouth and jaw.", preservation)

    def test_expression_default_preserves_the_mouth(self):
        # ASSET_SPEC 6: expression assets carry a REST mouth so visemes composite.
        self.write("expressions/happy-v1.0.md", """\
            ---
            id: happy
            version: 1.0
            kind: expression
            asset_name: happy
            task_target: the eyes and eyebrows
            ---

            ## TASK

            Change only the eyes and eyebrows.

            ## EXPRESSION

            Cheeks raised, eyes narrowed. Intensity: moderate.
            """)
        compiled = self.compile_json("expressions/happy-v1.0.md")["compiled"]
        kept = [line for line in compiled.splitlines() if "Keep the same person" in line][0]
        self.assertIn("mouth shape and position", kept)
        self.assertNotIn("eye shape and position", kept)

    def test_expression_preservation_omits_eyes_and_eyebrows(self):
        self.write("expressions/excited-v1.0.md", """\
            ---
            id: excited
            version: 1.0
            kind: expression
            asset_name: excited
            task_target: the eyes, eyebrows, and mouth
            touches: eyes, eyebrows, mouth
            ---

            ## TASK

            Change only the eyes, eyebrows, and mouth.

            ## EXPRESSION

            Eyes wide, brows raised, mouth open. Intensity: strong.
            """)
        compiled = self.compile_json("expressions/excited-v1.0.md")["compiled"]
        preservation = [c for c in compiled.split("\n\n") if c.startswith("PRESERVATION")][0]
        # Assert on the preserved list only - the trailing "except ..." line names
        # the touched features by design.
        kept = [line for line in preservation.splitlines()
                if "Keep the same person" in line][0]
        for dropped in ("eye shape and position", "eyebrows", "mouth shape and position"):
            self.assertNotIn(dropped, kept)
        self.assertIn("hairstyle and hair color", kept)

    def test_missing_task_target_is_an_error(self):
        self.write("visemes/mbp-v1.0.md", VISEME_MBP.replace(
            "task_target: the mouth and jaw\n", ""))
        result = self.run_cli("visemes/mbp-v1.0.md")
        self.assertEqual(result.returncode, 1)
        self.assertIn("task_target", result.stderr)

    def test_manual_preservation_is_used_verbatim(self):
        self.write("visemes/mbp-v1.0.md", VISEME_MBP.replace(
            "task_target: the mouth and jaw",
            "task_target: the mouth and jaw\npreservation: manual") + """
## PRESERVATION

The eyebrows in particular have drifted before. Hold them exactly.
""")
        compiled = self.compile_json("visemes/mbp-v1.0.md")["compiled"]
        self.assertIn("have drifted before", compiled)
        self.assertNotIn("Keep the same person", compiled)

    def test_preservation_block_without_manual_flag_is_an_error(self):
        self.write("visemes/mbp-v1.0.md", VISEME_MBP + """
## PRESERVATION

Something that would be silently discarded.
""")
        result = self.run_cli("visemes/mbp-v1.0.md")
        self.assertEqual(result.returncode, 1)
        self.assertIn("manual", result.stderr)

    # --- negatives -------------------------------------------------------

    def test_negatives_use_only_the_groups_for_the_kind(self):
        self.write("visemes/mbp-v1.0.md", VISEME_MBP)
        negative = self.compile_json("visemes/mbp-v1.0.md")["negative"]
        self.assertIn("different person", negative)          # identity
        self.assertIn("changed head size", negative)         # framing
        self.assertIn("changed eyebrows", negative)          # viseme
        self.assertIn("watermark", negative)                 # render

    def test_pose_negatives_omit_the_framing_group(self):
        self.write("poses/presenting-v1.0.md", """\
            ---
            id: presenting
            version: 1.0
            kind: pose
            asset_name: presenting
            camera_class: upper-body
            task_target: the body and arms
            ---

            ## TASK

            Change only the body and arms.
            """)
        negative = self.compile_json("poses/presenting-v1.0.md")["negative"]
        self.assertNotIn("changed camera distance", negative)
        self.assertIn("different person", negative)

    def test_negative_terms_for_touched_features_are_dropped(self):
        self.write("diagnostic/change-only-hair-v1.0.md", """\
            ---
            id: change-only-hair
            version: 1.0
            kind: diagnostic
            asset_name: change-only-hair
            seed: 1011
            task_target: the hair
            touches: hair
            ---

            ## TASK

            Change only the hair. Everything else is identical.
            """)
        negative = self.compile_json("diagnostic/change-only-hair-v1.0.md")["negative"]
        self.assertNotIn("different hairstyle", negative)
        self.assertNotIn("different hair color", negative)
        self.assertIn("different person", negative)
        self.assertIn("different clothing", negative)

    def test_moved_mouth_position_survives_a_mouth_task(self):
        # The mouth SHAPE changes for a viseme; the mouth POSITION must not.
        self.write("visemes/mbp-v1.0.md", VISEME_MBP)
        negative = self.compile_json("visemes/mbp-v1.0.md")["negative"]
        self.assertIn("moved mouth position", negative)

    # --- seeds -----------------------------------------------------------

    def test_seed_is_range_base_plus_canonical_index(self):
        cases = [
            ("visemes/rest-v1.0.md", "viseme", "REST", 20000),
            ("visemes/mbp-v1.0.md", "viseme", "MBP", 20008),
            ("visemes/n-v1.0.md", "viseme", "N", 20015),
            ("expressions/neutral-v1.0.md", "expression", "neutral", 10000),
            ("expressions/embarrassed-v1.0.md", "expression", "embarrassed", 10011),
            ("poses/neutral-v1.0.md", "pose", "neutral", 30000),
            ("poses/excited-v1.0.md", "pose", "excited", 30009),
        ]
        for relative, kind, name, expected in cases:
            with self.subTest(asset=relative):
                stem = Path(relative).stem.rsplit("-v", 1)[0]
                header = [
                    "---",
                    f"id: {stem}",
                    "version: 1.0",
                    f"kind: {kind}",
                    f"asset_name: {name}",
                ]
                if kind == "pose":
                    header.append("camera_class: medium")
                header += ["task_target: the target region", "---", "",
                           "## TASK", "", "Change only the target region.", ""]
                self.write(relative, "\n".join(header))
                self.assertEqual(self.compile_json(relative)["seed"], expected)

    def test_viseme_name_is_recorded_uppercase(self):
        self.write("visemes/mbp-v1.0.md", VISEME_MBP.replace("asset_name: MBP",
                                                             "asset_name: mbp"))
        self.assertEqual(self.compile_json("visemes/mbp-v1.0.md")["asset_name"], "MBP")

    def test_asset_name_outside_the_canonical_set_is_an_error(self):
        self.write("visemes/zz-v1.0.md", VISEME_MBP.replace("id: mbp", "id: zz")
                   .replace("asset_name: MBP", "asset_name: ZZ"))
        result = self.run_cli("visemes/zz-v1.0.md")
        self.assertEqual(result.returncode, 1)
        self.assertIn("canonical", result.stderr)

    def test_diagnostic_seed_outside_its_range_is_an_error(self):
        self.write("diagnostic/probe-v1.0.md", """\
            ---
            id: probe
            version: 1.0
            kind: diagnostic
            asset_name: probe
            seed: 20008
            task_target: the hair
            touches: hair
            ---

            ## TASK

            Change only the hair.
            """)
        result = self.run_cli("diagnostic/probe-v1.0.md")
        self.assertEqual(result.returncode, 1)
        self.assertIn("ADR-009", result.stderr)

    # --- lint ------------------------------------------------------------

    def lint(self):
        return self.run_cli("--lint")

    def test_lint_passes_on_valid_files(self):
        self.write("visemes/mbp-v1.0.md", VISEME_MBP)
        result = self.lint()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("OK", result.stdout)

    def test_lint_rejects_version_filename_mismatch(self):
        self.write("visemes/mbp-v1.0.md", VISEME_MBP.replace("version: 1.0", "version: 2.0"))
        result = self.lint()
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not match filename", result.stdout)

    def test_lint_rejects_unknown_block_name(self):
        self.write("visemes/mbp-v1.0.md", VISEME_MBP + "\n## MOOD\n\nCalm.\n")
        result = self.lint()
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown block", result.stdout)

    def test_lint_rejects_empty_block(self):
        self.write("visemes/mbp-v1.0.md", VISEME_MBP + "\n## POSE\n\n")
        result = self.lint()
        self.assertEqual(result.returncode, 1)
        self.assertIn("is empty", result.stdout)

    def test_lint_requires_exactly_one_task(self):
        self.write("visemes/mbp-v1.0.md", VISEME_MBP.replace("## TASK", "## OUTPUT", 1))
        result = self.lint()
        self.assertEqual(result.returncode, 1)
        self.assertIn("exactly one TASK", result.stdout)

    def test_lint_rejects_a_task_in_the_master_prompt(self):
        self.write("master/master-character-v1.0.md", MASTER + "\n## TASK\n\nMake it nice.\n")
        result = self.lint()
        self.assertEqual(result.returncode, 1)
        self.assertIn("never contains a TASK", result.stdout)

    def test_lint_rejects_filler_terms(self):
        self.write("visemes/mbp-v1.0.md", VISEME_MBP.replace(
            "jaw: closed", "jaw: closed, masterpiece, 8k"))
        result = self.lint()
        self.assertEqual(result.returncode, 1)
        self.assertIn("filler term", result.stdout)

    def test_lint_rejects_editing_operation_language(self):
        self.write("visemes/mbp-v1.0.md", VISEME_MBP.replace(
            "Change only the mouth and jaw.", "Inpaint the mouth region."))
        result = self.lint()
        self.assertEqual(result.returncode, 1)
        self.assertIn("editing-operation term", result.stdout)

    def test_lint_allows_mask_and_layer_as_visual_words(self):
        self.write("visemes/mbp-v1.0.md", VISEME_MBP.replace(
            "jaw: closed", "jaw: closed, wearing a cloth face mask in layers"))
        result = self.lint()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_lint_rejects_viseme_block_in_an_expression_prompt(self):
        self.write("expressions/happy-v1.0.md", """\
            ---
            id: happy
            version: 1.0
            kind: expression
            asset_name: happy
            task_target: the eyes and eyebrows
            ---

            ## TASK

            Change only the eyes and eyebrows.

            ## VISEME

            jaw: open
            """)
        result = self.lint()
        self.assertEqual(result.returncode, 1)
        self.assertIn("must not specify a viseme", result.stdout)

    def test_lint_rejects_expression_block_in_a_viseme_prompt(self):
        self.write("visemes/mbp-v1.0.md", VISEME_MBP + "\n## EXPRESSION\n\nSmiling.\n")
        result = self.lint()
        self.assertEqual(result.returncode, 1)
        self.assertIn("must not contain an EXPRESSION block", result.stdout)

    def test_lint_requires_a_valid_camera_class_on_poses(self):
        self.write("poses/presenting-v1.0.md", """\
            ---
            id: presenting
            version: 1.0
            kind: pose
            asset_name: presenting
            camera_class: extreme-close-up
            task_target: the body and arms
            ---

            ## TASK

            Change only the body and arms.
            """)
        result = self.lint()
        self.assertEqual(result.returncode, 1)
        self.assertIn("camera_class", result.stdout)

    def test_lint_rejects_unknown_touches(self):
        self.write("diagnostic/probe-v1.0.md", """\
            ---
            id: probe
            version: 1.0
            kind: diagnostic
            asset_name: probe
            seed: 1050
            task_target: the shoes
            touches: shoes
            ---

            ## TASK

            Change only the shoes.
            """)
        result = self.lint()
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown touches", result.stdout)

    def test_lint_requires_touches_on_diagnostics(self):
        self.write("diagnostic/probe-v1.0.md", """\
            ---
            id: probe
            version: 1.0
            kind: diagnostic
            asset_name: probe
            seed: 1050
            task_target: the hair
            ---

            ## TASK

            Change only the hair.
            """)
        result = self.lint()
        self.assertEqual(result.returncode, 1)
        self.assertIn("'touches' is required", result.stdout)

    def test_lint_rejects_a_duplicated_block(self):
        self.write("visemes/mbp-v1.0.md", VISEME_MBP + "\n## TASK\n\nAnd also this.\n")
        result = self.lint()
        self.assertEqual(result.returncode, 1)
        self.assertIn("appears twice", result.stdout)

    # --- CLI -------------------------------------------------------------

    def test_master_cannot_be_compiled_on_its_own(self):
        result = self.run_cli("master/master-character-v1.0.md")
        self.assertEqual(result.returncode, 1)
        self.assertIn("descriptive only", result.stderr)

    def test_missing_file_is_a_usage_error(self):
        result = self.run_cli("visemes/nope-v1.0.md")
        self.assertEqual(result.returncode, 2)

    def test_lint_with_a_named_file_is_a_usage_error(self):
        result = self.run_cli("visemes/mbp-v1.0.md", "--lint")
        self.assertEqual(result.returncode, 2)

    def test_json_record_carries_both_prompt_versions(self):
        self.write("visemes/mbp-v1.0.md", VISEME_MBP)
        record = self.compile_json("visemes/mbp-v1.0.md")
        self.assertEqual(record["master_version"], "master-character-v1.0")
        self.assertEqual(record["asset_prompt_version"], "mbp-v1.0")
        self.assertEqual(record["asset_type"], "viseme")


if __name__ == "__main__":
    unittest.main()
