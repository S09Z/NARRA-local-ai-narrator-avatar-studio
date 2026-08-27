#!/usr/bin/env python3
"""Tests for scripts/validation/lock_library.py (PHASE 6).

This is the gate that decides whether video work may begin, so the ways it has to
refuse matter more than the way it passes. Each test builds a complete, passing
library in a throwaway tree and then breaks exactly one thing.

Run:
    python3 -m unittest discover -s tests -p 'test_*.py' -v
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "validation" / "lock_library.py"
SHEETS = REPO / "scripts" / "utilities" / "contact_sheet.py"

sys.path.insert(0, str(REPO / "scripts" / "lib"))
import canon                                          # noqa: E402
from imagecheck import sha256                         # noqa: E402

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    Image = None

ANCHOR = {"anchor_x": 0.500, "anchor_y": 0.640, "mouth_width": 0.140,
          "mouth_height": 0.070}
EDIT_REGION = {"left": 0.40, "top": 0.58, "right": 0.60, "bottom": 0.70}
STAMP = "2026-08-25T00:00:00+00:00"
SUBDIR = {"expression": "expressions", "viseme": "visemes", "pose": "poses"}


def draw_character(path, mouth=False, offset=0):
    """An opaque blob on transparent - stands in for a character cutout."""
    image = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse([300, 200 + offset, 724, 800 + offset], fill=(230, 200, 180, 255))
    if mouth:
        # Inside EDIT_REGION, so a viseme's changed pixels stay contained (ADR-013).
        draw.rectangle([440, 610, 584, 690], fill=(90, 50, 50, 255))
    image.save(path)
    return path


@unittest.skipIf(Image is None, "Pillow is required for these tests")
class LockLibraryTest(unittest.TestCase):

    # --- fixture ----------------------------------------------------------

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        for sub in ("character/reference", "character/expressions", "character/visemes",
                    "character/poses", "character/bible", "character/compositions",
                    "metadata/validation", "metadata/generations",
                    "assets/contact-sheets", "docs"):
            (self.repo / sub).mkdir(parents=True)

        # The pose prompts declare the camera classes the metadata is checked against,
        # and the compositions name real assets - both are inputs, not fixtures.
        shutil.copytree(REPO / "prompts" / "poses", self.repo / "prompts" / "poses")
        shutil.copy(REPO / "character" / "compositions" / "narrator-states.json",
                    self.repo / "character" / "compositions" / "narrator-states.json")

        self.write_reference()
        self.write_anchor()
        for asset_type in ("expression", "viseme", "pose"):
            for name in canon.CANONICAL[asset_type]:
                self.write_asset(asset_type, name)
        self.build_sheets()

    def write_reference(self):
        directory = self.repo / "character" / "reference"
        master = draw_character(directory / "narra-reference-master-v1.png")
        (directory / "master.png").write_bytes(master.read_bytes())
        sidecar = json.dumps({"character": "narra", "asset_type": "reference",
                              "sha256": sha256(master)}, indent=2) + "\n"
        (directory / "narra-reference-master-v1.json").write_text(sidecar)
        (self.repo / "metadata" / "generations"
         / "narra-reference-master-v1.json").write_text(sidecar)

    def write_anchor(self, measured=True):
        (self.repo / "character" / "bible" / "mouth-anchor.json").write_text(json.dumps({
            "character": "narra",
            "status": "measured" if measured else "unmeasured",
            "anchor": ANCHOR if measured else dict.fromkeys(ANCHOR),
            "edit_region": EDIT_REGION if measured else None,
        }, indent=2))

    def camera_class(self, pose):
        for line in (self.repo / "prompts" / "poses" / f"{pose}-v1.0.md").read_text().splitlines():
            if line.startswith("camera_class:"):
                return line.split(":", 1)[1].strip()
        return None

    def asset_path(self, asset_type, name):
        return (self.repo / "character" / SUBDIR[asset_type]
                / canon.asset_filename(asset_type, name))

    def write_asset(self, asset_type, name, offset=0):
        path = self.asset_path(asset_type, name)
        draw_character(path, mouth=(asset_type == "viseme"), offset=offset)
        canonical = canon.canonical_name(asset_type, name)
        data = {
            "character": "narra",
            "asset_type": asset_type,
            "asset_name": canonical,
            "version": 1,
            "file": f"character/{SUBDIR[asset_type]}/{path.name}",
            "reference": "character/reference/narra-reference-master-v1.png",
            "sha256": sha256(path),
            "model": {"name": "FLUX.2 Klein 4B Base", "precision": "fp8",
                      "file": "flux2-klein-4b-base-fp8.safetensors"},
            "workflow": {"file": f"workflows/{asset_type}/{asset_type}-v1.json",
                         "version": "1.0"},
            "prompt": {"master_version": "master-character-v1.0",
                       "asset_prompt_version": f"{name.lower()}-v1.0",
                       "compiled": "<compiled prompt>", "negative": "<negative>"},
            "generation": {"seed": canon.derive_seed(asset_type, name), "steps": 20,
                           "cfg": 3.5, "sampler": "euler", "scheduler": "simple",
                           "denoise": 0.45, "resolution": [1024, 1024]},
            "mouth_anchor": ANCHOR,
            "environment": {"comfyui_version": "0.3.40", "custom_nodes": []},
            "validation": {"status": "approved", "validated_at": STAMP, "notes": ""},
            "generated_at": STAMP,
        }
        if asset_type == "pose":
            data["camera_class"] = self.camera_class(name)
        path.with_suffix(".json").write_text(json.dumps(data, indent=2) + "\n")
        self.write_review(asset_type, canonical, path)
        return path

    def write_review(self, asset_type, name, path, overall="approved"):
        (self.repo / "metadata" / "validation" / f"{path.stem}.json").write_text(json.dumps({
            "asset": f"character/{SUBDIR[asset_type]}/{path.name}",
            "asset_type": asset_type,
            "asset_name": name,
            "validated_at": STAMP,
            "automated": {"status": "passed", "counts": {"PASS": 1}, "checks": []},
            "human_review": {"status": "approved" if overall == "approved" else "pending",
                             "reviewer": "tester" if overall == "approved" else "",
                             "reviewed_at": STAMP if overall == "approved" else "",
                             "notes": ""},
            "overall": overall,
        }, indent=2))

    def build_sheets(self):
        result = self.run_script(SHEETS, "--all")
        self.assertEqual(result.returncode, 0, result.stderr)

    # --- helpers ----------------------------------------------------------

    def run_script(self, script, *args):
        return subprocess.run([sys.executable, str(script), *args],
                              capture_output=True, text=True,
                              env=dict(os.environ, NARRA_REPO=str(self.repo)))

    def gate(self, *args):
        return self.run_script(SCRIPT, *args)

    def assertGatePasses(self):
        result = self.gate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("GATE PASSED", result.stdout)
        return result

    def assertGateFails(self, needle):
        result = self.gate()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("GATE FAILED", result.stdout)
        self.assertIn(needle, result.stdout)
        return result

    # --- the gate ---------------------------------------------------------

    def test_complete_library_passes_the_gate(self):
        result = self.assertGatePasses()
        self.assertIn("38 assets", result.stdout)

    def test_missing_asset_fails_completeness(self):
        self.asset_path("viseme", "SH").unlink()
        self.assertGateFails("missing: SH")

    def test_short_canonical_set_would_move_the_finish_line(self):
        self.assertEqual(canon.REQUIRED_COUNTS,
                         {"expression": 12, "viseme": 16, "pose": 10})
        self.assertEqual([len(canon.CANONICAL[t]) for t in ("expression", "viseme", "pose")],
                         [12, 16, 10])

    def test_stray_asset_fails(self):
        stray = self.repo / "character" / "expressions" / "narra-expression-smug-v1.png"
        draw_character(stray)
        self.assertGateFails("not in the canonical expression set")

    def test_asset_without_a_review_record_cannot_be_locked(self):
        path = self.asset_path("expression", "happy")
        (self.repo / "metadata" / "validation" / f"{path.stem}.json").unlink()
        self.assertGateFails("no QC record")

    def test_asset_pending_human_review_cannot_be_locked(self):
        path = self.asset_path("expression", "happy")
        self.write_review("expression", "happy", path, overall="pending-human-review")
        self.assertGateFails("not approved")

    def test_unmeasured_anchor_fails(self):
        self.write_anchor(measured=False)
        self.assertGateFails("mouth anchor is unmeasured")

    def test_missing_reference_fails(self):
        (self.repo / "character" / "reference" / "narra-reference-master-v1.png").unlink()
        self.assertGateFails("reference/master")

    def test_missing_contact_sheet_fails(self):
        (self.repo / "assets" / "contact-sheets"
         / "narra-sheet-visemes-v1.png").unlink()
        self.assertGateFails("narra-sheet-visemes-v1.png missing")

    def test_broken_metadata_fails_the_asset(self):
        path = self.asset_path("pose", "confident")
        data = json.loads(path.with_suffix(".json").read_text())
        data["generation"]["seed"] = 12345
        path.with_suffix(".json").write_text(json.dumps(data, indent=2))
        self.assertGateFails("pose/confident")

    def test_pose_crown_spread_within_a_camera_class_is_checked(self):
        # `explaining` and `neutral` are both medium; move one crown 40px down.
        self.write_asset("pose", "explaining", offset=40)
        self.assertGateFails("crown spread")

    def test_pose_framing_is_not_measured_against_the_closeup_reference(self):
        # Every pose is medium or wider, so a reference comparison would fail them all.
        result = self.assertGatePasses()
        self.assertNotIn("silhouette top moved", result.stdout)

    # --- locking ----------------------------------------------------------

    def test_lock_requires_a_name(self):
        result = self.gate("--lock")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--by", result.stderr)

    def test_lock_writes_the_manifest_mirrors_and_baseline(self):
        result = self.gate("--lock", "--by", "tester")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        lock = json.loads((self.repo / "metadata" / "production-lock.json").read_text())
        self.assertEqual(lock["lock_version"], 1)
        self.assertEqual(lock["locked_by"], "tester")
        self.assertEqual(lock["resolution"], [1024, 1024])
        self.assertEqual([lock["sets"][t]["locked"] for t in ("expression", "viseme", "pose")],
                         [12, 16, 10])

        viseme = next(record for record in lock["sets"]["viseme"]["assets"]
                      if record["name"] == "MBP")
        self.assertEqual(viseme["seed"], canon.derive_seed("viseme", "MBP"))
        self.assertEqual(viseme["prompt_version"], "mbp-v1.0")
        self.assertEqual(viseme["reviewed_by"], "tester")
        self.assertEqual(viseme["sha256"], sha256(self.asset_path("viseme", "MBP")))

        pose = next(record for record in lock["sets"]["pose"]["assets"]
                    if record["name"] == "confident")
        self.assertEqual(pose["camera_class"], "three-quarter")

        mirror = (self.repo / "metadata" / "generations"
                  / "narra-viseme-mbp-v1.json")
        self.assertTrue(mirror.exists())
        self.assertEqual(mirror.read_text(),
                         self.asset_path("viseme", "MBP").with_suffix(".json").read_text())

        baseline = (self.repo / "docs" / "production-baseline.md").read_text()
        self.assertIn("**LOCKED**", baseline)
        self.assertIn("FLUX.2 Klein 4B Base", baseline)
        self.assertIn("master-character-v1.0", baseline)
        self.assertIn("PHASE 7", baseline)

    def test_relocking_increments_the_lock_version(self):
        self.gate("--lock", "--by", "tester")
        self.gate("--lock", "--by", "tester")
        lock = json.loads((self.repo / "metadata" / "production-lock.json").read_text())
        self.assertEqual(lock["lock_version"], 2)

    def test_gate_failure_writes_nothing(self):
        self.asset_path("pose", "presenting").unlink()
        result = self.gate("--lock", "--by", "tester")
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.repo / "metadata" / "production-lock.json").exists())

    def test_baseline_without_a_lock_says_so(self):
        result = self.gate("--baseline")
        self.assertEqual(result.returncode, 0)
        baseline = (self.repo / "docs" / "production-baseline.md").read_text()
        self.assertIn("**NOT LOCKED.**", baseline)

    # --- verification -----------------------------------------------------

    def test_verify_passes_directly_after_locking(self):
        self.gate("--lock", "--by", "tester")
        result = self.gate("--verify")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("matches its lock", result.stdout)

    def test_verify_detects_an_edited_asset(self):
        self.gate("--lock", "--by", "tester")
        draw_character(self.asset_path("expression", "proud"), offset=3)
        result = self.gate("--verify")
        self.assertEqual(result.returncode, 1)
        self.assertIn("sha256 differs from the lock", result.stdout)

    def test_verify_detects_a_changed_reference(self):
        self.gate("--lock", "--by", "tester")
        draw_character(self.repo / "character" / "reference"
                       / "narra-reference-master-v1.png", offset=5)
        result = self.gate("--verify")
        self.assertEqual(result.returncode, 1)
        self.assertIn("the reference changed since the lock", result.stdout)

    def test_verify_without_a_lock_fails(self):
        result = self.gate("--verify")
        self.assertEqual(result.returncode, 1)
        self.assertIn("nothing has been locked yet", result.stdout)

    # --- upscale derivatives (ASSET_SPEC 1, ADR-017) ----------------------

    def write_upscale(self, master, stem=None, derived_from=None, digest=None):
        directory = self.repo / "assets" / "approved" / "upscaled"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{stem or master.stem + '-up2048'}.png"
        image = Image.new("RGBA", (2048, 2048), (0, 0, 0, 0))
        ImageDraw.Draw(image).ellipse([600, 400, 1448, 1600], fill=(230, 200, 180, 255))
        image.save(path)
        path.with_suffix(".json").write_text(json.dumps({
            "derived_from": derived_from if derived_from is not None
            else f"character/{SUBDIR['expression']}/{master.name}",
            "derived_from_sha256": digest if digest is not None else sha256(master),
            "resolution": [2048, 2048],
            "upscaler": "4x-UltraSharp",
        }, indent=2))
        return path

    def test_valid_upscale_is_recorded_in_the_lock(self):
        self.write_upscale(self.asset_path("expression", "neutral"))
        self.assertGatePasses()
        self.gate("--lock", "--by", "tester")
        lock = json.loads((self.repo / "metadata" / "production-lock.json").read_text())
        self.assertEqual(len(lock["upscales"]), 1)
        self.assertEqual(lock["upscales"][0]["upscaler"], "4x-UltraSharp")

    def test_upscale_of_a_stale_master_fails(self):
        self.write_upscale(self.asset_path("expression", "neutral"), digest="0" * 64)
        self.assertGateFails("upscaled from a version of the asset that no longer exists")

    def test_upscale_without_a_master_fails(self):
        master = self.asset_path("expression", "neutral")
        self.write_upscale(master, stem="narra-expression-smug-v1-up2048",
                           derived_from="character/expressions/narra-expression-smug-v1.png")
        self.assertGateFails("is not an approved master in the locked library")


if __name__ == "__main__":
    unittest.main()
