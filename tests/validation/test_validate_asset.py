#!/usr/bin/env python3
"""Tests for scripts/validation/validate_asset.py (PHASE 3.4).

This validator is the gate that decides what enters the production library, so
each way an asset can be wrong is pinned individually.

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
SCRIPT = REPO / "scripts" / "validation" / "validate_asset.py"

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    Image = None


def draw_character(path, offset=0):
    """An opaque blob on transparent - stands in for a character cutout."""
    image = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse([300, 200 + offset, 724, 800 + offset], fill=(230, 200, 180, 255))
    image.save(path)
    return path


@unittest.skipIf(Image is None, "Pillow is required for these tests")
class ValidateAssetTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        for sub in ("character/reference", "character/expressions", "character/visemes",
                    "character/poses", "character/bible", "metadata/validation"):
            (self.repo / sub).mkdir(parents=True)
        self.reference = draw_character(
            self.repo / "character" / "reference" / "narra-reference-master-v1.png")
        self.anchor_file = self.repo / "character" / "bible" / "mouth-anchor.json"
        self.write_anchor(measured=False)
        self.addCleanup(self._tmp.cleanup)

    def write_anchor(self, measured, anchor_x=0.500, anchor_y=0.640):
        self.anchor_file.write_text(json.dumps({
            "status": "measured" if measured else "unmeasured",
            "anchor": ({"anchor_x": anchor_x, "anchor_y": anchor_y,
                        "mouth_width": 0.14, "mouth_height": 0.07}
                       if measured else
                       {"anchor_x": None, "anchor_y": None,
                        "mouth_width": None, "mouth_height": None}),
        }, indent=2))

    def sidecar_for(self, path, asset_type, asset_name, seed, **overrides):
        import hashlib
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        data = {
            "character": "narra",
            "asset_type": asset_type,
            "asset_name": asset_name,
            "version": 1,
            "file": f"character/{asset_type}s/{path.name}",
            "reference": "character/reference/narra-reference-master-v1.png",
            "sha256": digest,
            "model": {"name": "FLUX.2 Klein 4B Base", "precision": "fp8"},
            "workflow": {"file": "workflows/expression/expression-v1.json", "version": "1.0"},
            "prompt": {"master_version": "master-character-v1.0",
                       "asset_prompt_version": f"{asset_name.lower()}-v1.0",
                       "compiled": "...", "negative": "..."},
            "generation": {"seed": seed, "steps": 20, "resolution": [1024, 1024]},
            "mouth_anchor": {"anchor_x": None, "anchor_y": None,
                             "mouth_width": None, "mouth_height": None},
            "environment": {"comfyui_version": "0.3.0", "custom_nodes": []},
            "validation": {"status": "pending", "validated_at": "", "notes": ""},
            "generated_at": "2026-08-25T00:00:00+00:00",
        }
        data.update(overrides)
        path.with_suffix(".json").write_text(json.dumps(data, indent=2))
        return data

    def make_asset(self, asset_type="expression", asset_name="happy", seed=10002,
                   offset=0, filename=None, sidecar=True, **overrides):
        filename = filename or f"narra-{asset_type}-{asset_name.lower()}-v1.png"
        path = self.repo / "character" / f"{asset_type}s" / filename
        draw_character(path, offset=offset)
        if sidecar:
            self.sidecar_for(path, asset_type, asset_name, seed, **overrides)
        return path

    def run_cli(self, *args):
        env = dict(os.environ, NARRA_REPO=str(self.repo))
        return subprocess.run([sys.executable, str(SCRIPT), *[str(a) for a in args]],
                              capture_output=True, text=True, env=env)

    # --- happy path ------------------------------------------------------

    def test_conforming_asset_passes(self):
        path = self.make_asset()
        result = self.run_cli(path)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Automated checks passed", result.stdout)

    def test_pass_is_not_an_approval(self):
        path = self.make_asset()
        result = self.run_cli(path)
        self.assertIn("NOT an approval", result.stdout)
        self.assertIn("Distinct from every other expression", result.stdout)

    def test_failure_does_not_print_the_human_checklist(self):
        path = self.make_asset(seed=99999)
        result = self.run_cli(path)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("NOT an approval", result.stdout)

    # --- naming ----------------------------------------------------------

    def test_filename_not_matching_the_convention_fails(self):
        path = self.make_asset(filename="happy.png", sidecar=False)
        result = self.run_cli(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("naming/pattern", result.stdout)

    def test_non_canonical_asset_name_fails(self):
        path = self.make_asset(asset_name="delighted", seed=10002,
                               filename="narra-expression-delighted-v1.png")
        result = self.run_cli(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("naming/canonical", result.stdout)

    def test_asset_outside_its_directory_warns_but_does_not_fail(self):
        path = self.repo / "character" / "visemes" / "narra-expression-happy-v1.png"
        draw_character(path)
        self.sidecar_for(path, "expression", "happy", 10002)
        result = self.run_cli(path)
        self.assertIn("[WARN] naming/location", result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)

    # --- metadata --------------------------------------------------------

    def test_missing_sidecar_fails(self):
        path = self.make_asset(sidecar=False)
        result = self.run_cli(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("metadata/sidecar", result.stdout)

    def test_missing_mandatory_field_fails(self):
        path = self.make_asset()
        data = json.loads(path.with_suffix(".json").read_text())
        del data["workflow"]
        path.with_suffix(".json").write_text(json.dumps(data))
        result = self.run_cli(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("metadata/mandatory", result.stdout)

    def test_wrong_seed_fails(self):
        path = self.make_asset(seed=10007)      # 10007 is 'confused', not 'happy'
        result = self.run_cli(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("metadata/seed", result.stdout)
        self.assertIn("10002", result.stdout)

    def test_seed_matches_canonical_index_for_every_expression(self):
        for index, name in enumerate([
                "neutral", "friendly", "happy", "excited", "serious", "concerned",
                "surprised", "confused", "thinking", "explaining", "proud",
                "embarrassed"]):
            with self.subTest(expression=name):
                path = self.make_asset(asset_name=name, seed=10000 + index)
                result = self.run_cli(path)
                self.assertEqual(result.returncode, 0, result.stdout)

    def test_metadata_disagreeing_with_the_filename_fails(self):
        path = self.make_asset(asset_name="happy", seed=10002)
        self.sidecar_for(path, "expression", "serious", 10002)
        result = self.run_cli(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("filename-agreement", result.stdout)

    def test_sha256_not_matching_the_image_fails(self):
        path = self.make_asset()
        data = json.loads(path.with_suffix(".json").read_text())
        data["sha256"] = "0" * 64
        path.with_suffix(".json").write_text(json.dumps(data))
        result = self.run_cli(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("metadata/sha256", result.stdout)

    def test_wrong_reference_fails(self):
        path = self.make_asset()
        data = json.loads(path.with_suffix(".json").read_text())
        data["reference"] = "character/reference/narra-reference-master-v2.png"
        path.with_suffix(".json").write_text(json.dumps(data))
        result = self.run_cli(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("metadata/reference", result.stdout)

    # --- drift -----------------------------------------------------------

    def test_head_drift_within_tolerance_passes(self):
        path = self.make_asset(offset=5)        # 5px of 1024 = 0.49%, under 1%
        result = self.run_cli(path)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("[PASS] drift/head", result.stdout)

    def test_head_drift_beyond_tolerance_fails(self):
        path = self.make_asset(offset=40)       # 40px of 1024 = 3.9%
        result = self.run_cli(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("drift/head", result.stdout)

    def test_anchor_check_skips_while_unmeasured(self):
        path = self.make_asset()
        result = self.run_cli(path)
        self.assertIn("[SKIP] drift/anchor", result.stdout)

    def test_measured_anchor_missing_from_metadata_fails(self):
        self.write_anchor(measured=True)
        path = self.make_asset()
        result = self.run_cli(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("records no mouth_anchor", result.stdout)

    def test_anchor_drift_within_tolerance_passes(self):
        self.write_anchor(measured=True)
        path = self.make_asset()
        data = json.loads(path.with_suffix(".json").read_text())
        data["mouth_anchor"] = {"anchor_x": 0.502, "anchor_y": 0.641,
                                "mouth_width": 0.14, "mouth_height": 0.07}
        path.with_suffix(".json").write_text(json.dumps(data))
        result = self.run_cli(path)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("[PASS] drift/anchor", result.stdout)

    def test_anchor_drift_beyond_tolerance_fails(self):
        self.write_anchor(measured=True)
        path = self.make_asset()
        data = json.loads(path.with_suffix(".json").read_text())
        data["mouth_anchor"] = {"anchor_x": 0.530, "anchor_y": 0.640,
                                "mouth_width": 0.14, "mouth_height": 0.07}
        path.with_suffix(".json").write_text(json.dumps(data))
        result = self.run_cli(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("will not composite", result.stdout)

    # --- recording -------------------------------------------------------

    def test_record_writes_a_validation_record(self):
        path = self.make_asset()
        result = self.run_cli(path, "--record")
        self.assertEqual(result.returncode, 0, result.stdout)
        record = self.repo / "metadata" / "validation" / f"{path.stem}.json"
        self.assertTrue(record.exists())
        data = json.loads(record.read_text())
        self.assertEqual(data["automated"]["status"], "passed")
        self.assertEqual(data["human_review"]["status"], "pending")
        self.assertEqual(data["overall"], "pending-human-review")

    def test_record_of_a_failure_is_marked_failed(self):
        path = self.make_asset(seed=99999)
        self.run_cli(path, "--record")
        record = self.repo / "metadata" / "validation" / f"{path.stem}.json"
        data = json.loads(record.read_text())
        self.assertEqual(data["overall"], "failed")

    # --- set completeness ------------------------------------------------

    def test_incomplete_set_fails(self):
        self.make_asset(asset_name="happy", seed=10002)
        result = self.run_cli("--set", "expression")
        self.assertEqual(result.returncode, 1)
        self.assertIn("1/12 present", result.stdout)
        self.assertIn("cannot be locked", result.stdout)

    def test_complete_set_passes(self):
        for index, name in enumerate([
                "neutral", "friendly", "happy", "excited", "serious", "concerned",
                "surprised", "confused", "thinking", "explaining", "proud",
                "embarrassed"]):
            self.make_asset(asset_name=name, seed=10000 + index)
        result = self.run_cli("--set", "expression")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("12/12 present", result.stdout)

    def test_stray_asset_in_a_set_fails(self):
        self.make_asset(asset_name="happy", seed=10002)
        draw_character(self.repo / "character" / "expressions" / "narra-expression-smug-v1.png")
        result = self.run_cli("--set", "expression")
        self.assertEqual(result.returncode, 1)
        self.assertIn("STRAY", result.stdout)

    def test_unknown_set_is_a_usage_error(self):
        result = self.run_cli("--set", "gestures")
        self.assertEqual(result.returncode, 2)

    def test_missing_asset_is_a_usage_error(self):
        result = self.run_cli(self.repo / "character" / "expressions" / "nope.png")
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
