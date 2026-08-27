#!/usr/bin/env python3
"""Tests for scripts/animation/build_animation.py and render_frames.py (PHASE 8).

The render tests build a complete synthetic repository - anchor, expressions, visemes,
narrator states - and drive the real CLI against it through NARRA_REPO. That exercises
the whole path from Thai text to PNG frames on disk without needing the image library
that does not exist yet.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BUILD_TIMELINE = REPO / "scripts" / "audio" / "build_timeline.py"
BUILD_ANIMATION = REPO / "scripts" / "animation" / "build_animation.py"
RENDER = REPO / "scripts" / "animation" / "render_frames.py"
VALIDATE = REPO / "scripts" / "validation" / "validate_animation.py"

sys.path.insert(0, str(REPO / "scripts" / "lib"))
import canon             # noqa: E402
import compositor as compositor_lib  # noqa: E402

try:
    from PIL import Image
    HAVE_PILLOW = True
except ImportError:                    # pragma: no cover
    HAVE_PILLOW = False

REGION = {"left": 0.35, "top": 0.56, "right": 0.65, "bottom": 0.78}
STATES = json.loads((REPO / "character" / "compositions"
                     / "narrator-states.json").read_text(encoding="utf-8"))


def run(script, *args, env=None):
    environment = dict(os.environ)
    if env:
        environment.update(env)
    return subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True, env=environment)


class BuildAnimationTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.work = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.timeline = self.work / "t.json"
        result = run(BUILD_TIMELINE, "สวัสดีครับ ผมชื่อนารา",
                     "--out", str(self.timeline))
        self.assertEqual(result.returncode, 0, result.stderr)

    def build(self, *extra):
        out = self.work / "a.json"
        result = run(BUILD_ANIMATION, str(self.timeline), "--out", str(out), *extra)
        self.assertEqual(result.returncode, 0, result.stderr)
        return out, json.loads(out.read_text(encoding="utf-8"))

    def test_builds_a_plan_from_a_timeline(self):
        _, plan = self.build()
        self.assertEqual(plan["state"], "talking")
        self.assertTrue(plan["tracks"]["mouth"])

    def test_fps_is_honoured(self):
        _, plan = self.build("--fps", "30")
        self.assertEqual(plan["fps"], 30)
        self.assertAlmostEqual(plan["frame_count"] / 30, plan["duration"], delta=0.05)

    def test_a_static_state_produces_no_mouth_layers(self):
        _, plan = self.build("--state", "reaction")
        self.assertEqual(plan["mouth_mode"], "static")
        self.assertTrue(all(not frame["layers"] for frame in plan["tracks"]["mouth"]))

    def test_an_unknown_state_fails(self):
        result = run(BUILD_ANIMATION, str(self.timeline), "--out",
                     str(self.work / "x.json"), "--state", "nope")
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown state", result.stderr)

    def test_an_open_mouth_expression_plan_is_refused(self):
        plan_file = self.work / "plan.json"
        plan_file.write_text(json.dumps(
            [{"start": 0.0, "end": 1.0, "expression": "surprised"}]), encoding="utf-8")
        result = run(BUILD_ANIMATION, str(self.timeline), "--out",
                     str(self.work / "x.json"), "--expression-plan", str(plan_file))
        self.assertEqual(result.returncode, 1)
        self.assertIn("two mouths", result.stderr)

    def test_the_plan_validates(self):
        out, _ = self.build()
        result = run(VALIDATE, str(out))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_rebuilding_is_reproducible(self):
        _, first = self.build()
        _, second = self.build()
        self.assertEqual(first["digest"], second["digest"])

    def test_text_input_runs_phase_7_inline(self):
        out = self.work / "inline.json"
        result = run(BUILD_ANIMATION, "--text", "สวัสดีครับ", "--out", str(out))
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(plan["source_timeline"]["timing_source"], "estimated")


@unittest.skipUnless(HAVE_PILLOW, "Pillow is required to render")
class RenderFramesTest(unittest.TestCase):
    """The full path, against a synthetic asset library."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

        anchor = self.repo / "character" / "bible" / "mouth-anchor.json"
        anchor.parent.mkdir(parents=True)
        anchor.write_text(json.dumps({
            "character": "narra", "status": "measured", "version": 1,
            "anchor": {"anchor_x": 0.5, "anchor_y": 0.64},
            "edit_region": REGION}), encoding="utf-8")
        self.box = compositor_lib.edit_box(
            json.loads(anchor.read_text(encoding="utf-8")))

        states = self.repo / "character" / "compositions" / "narrator-states.json"
        states.parent.mkdir(parents=True)
        states.write_text(json.dumps(STATES), encoding="utf-8")

        expressions = self.repo / "character" / "expressions"
        visemes = self.repo / "character" / "visemes"
        expressions.mkdir(parents=True)
        visemes.mkdir(parents=True)
        for name in canon.EXPRESSIONS:
            self._write(expressions / canon.asset_filename("expression", name),
                        (200, 170, 150, 255))
        for index, name in enumerate(canon.VISEMES):
            self._write(visemes / canon.asset_filename("viseme", name),
                        (10 + index * 15, 40, 40, 255))

        self.env = {"NARRA_REPO": str(self.repo)}
        self.timeline = self.repo / "t.json"
        self.assertEqual(run(BUILD_TIMELINE, "สวัสดีครับ ผมชื่อนารา",
                             "--out", str(self.timeline), env=self.env).returncode, 0)
        self.animation = self.repo / "a.json"
        result = run(BUILD_ANIMATION, str(self.timeline), "--out", str(self.animation),
                     env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)

    def _write(self, path, mouth):
        image = Image.new("RGBA", (1024, 1024), (200, 170, 150, 255))
        image.paste(Image.new("RGBA", (self.box[2] - self.box[0],
                                       self.box[3] - self.box[1]), mouth), self.box)
        image.save(path)

    def test_check_reports_all_assets_present(self):
        result = run(RENDER, str(self.animation), "--check", env=self.env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("all required assets are present", result.stdout)

    def test_check_reports_a_missing_asset(self):
        (self.repo / "character" / "visemes"
         / canon.asset_filename("viseme", "REST")).unlink()
        result = run(RENDER, str(self.animation), "--check", env=self.env)
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing", result.stdout)

    def test_renders_one_png_per_frame(self):
        out_dir = self.repo / "frames"
        result = run(RENDER, str(self.animation), "--out-dir", str(out_dir),
                     env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(self.animation.read_text(encoding="utf-8"))
        self.assertEqual(len(list(out_dir.glob("frame-*.png"))), plan["frame_count"])

    def test_rendered_frames_are_the_right_size_and_mode(self):
        out_dir = self.repo / "frames"
        run(RENDER, str(self.animation), "--out-dir", str(out_dir),
            "--range", "0:3", env=self.env)
        for path in sorted(out_dir.glob("frame-*.png")):
            with Image.open(path) as image:
                self.assertEqual(image.size, (1024, 1024))
                self.assertEqual(image.mode, "RGBA")

    def test_a_range_renders_only_that_range(self):
        out_dir = self.repo / "frames"
        run(RENDER, str(self.animation), "--out-dir", str(out_dir),
            "--range", "5:9", env=self.env)
        names = sorted(path.name for path in out_dir.glob("frame-*.png"))
        self.assertEqual(names, ["frame-000005.png", "frame-000006.png",
                                 "frame-000007.png", "frame-000008.png"])

    def test_the_face_outside_the_mouth_is_untouched_in_a_rendered_frame(self):
        out_dir = self.repo / "frames"
        run(RENDER, str(self.animation), "--out-dir", str(out_dir),
            "--range", "0:2", env=self.env)
        with Image.open(out_dir / "frame-000000.png") as image:
            self.assertEqual(image.getpixel((5, 5)), (200, 170, 150, 255))
            self.assertEqual(image.getpixel((1000, 1000)), (200, 170, 150, 255))

    def test_a_contact_sheet_can_be_written(self):
        sheet = self.repo / "sheet.png"
        result = run(RENDER, str(self.animation), "--out-dir", str(self.repo / "f"),
                     "--range", "0:8", "--contact-sheet", str(sheet), env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(sheet.exists())


if __name__ == "__main__":
    unittest.main()
