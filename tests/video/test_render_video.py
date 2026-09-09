#!/usr/bin/env python3
"""Tests for scripts/video/render_video.py (PHASE 9).

ffmpeg is not installed on every machine this runs on, and the image library does
not exist at all yet, so the parts that must be testable without either are the
parts tested here: the requirement probe, the geometry, the compositing, and the
exact ffmpeg call as a value rather than as a side effect.

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
SCRIPT = REPO / "scripts" / "video" / "render_video.py"
sys.path.insert(0, str(REPO / "scripts" / "video"))
sys.path.insert(0, str(REPO / "scripts" / "lib"))
sys.path.insert(0, str(REPO / "tests"))

import render_video                                   # noqa: E402
import videoplan                                      # noqa: E402
from video import fixtures                            # noqa: E402

try:
    from PIL import Image
except ImportError:                                    # pragma: no cover
    Image = None


def levels(report, name):
    return [level for level, entry, _ in report.rows if entry == name]


class Fixture(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        timeline = fixtures.timeline()
        self.plan = videoplan.build(fixtures.animation(timeline), timeline, name="demo")

    def frames(self, count=None, size=1024):
        directory = self.tmp / "frames"
        directory.mkdir(exist_ok=True)
        for index in range(count if count is not None else self.plan["frame_count"]):
            Image.new("RGBA", (size, size), (10, 20, 30, 255)).save(
                directory / f"frame-{index:06d}.png")
        return directory


@unittest.skipIf(Image is None, "Pillow is required")
class ProbeTest(Fixture):

    def test_missing_frames_block_a_render(self):
        report = render_video.probe(self.plan, self.tmp / "nothing")
        self.assertIn("FAIL", levels(report, "need/frames"))
        self.assertTrue(report.failed())

    def test_too_few_frames_block_a_render(self):
        report = render_video.probe(self.plan, self.frames(count=3))
        self.assertIn("FAIL", levels(report, "need/frames"))

    def test_a_complete_frame_set_passes(self):
        report = render_video.probe(self.plan, self.frames())
        self.assertIn("PASS", levels(report, "need/frames"))

    def test_a_missing_audio_file_blocks_a_render(self):
        plan = dict(self.plan, audio={"path": str(self.tmp / "gone.wav")})
        self.assertIn("FAIL", levels(render_video.probe(plan, self.frames()),
                                     "need/audio"))

    def test_no_audio_at_all_is_only_a_warning(self):
        plan = dict(self.plan, audio={})
        self.assertIn("WARN", levels(render_video.probe(plan, self.frames()),
                                     "need/audio"))

    def test_burn_in_requires_an_ass_sidecar(self):
        plan = json.loads(json.dumps(self.plan))
        plan["subtitles"]["burn_in"] = True
        self.assertIn("FAIL", levels(render_video.probe(plan, self.frames()),
                                     "need/sidecar"))

    def test_sidecar_check_is_skipped_when_not_burning_in(self):
        self.assertIn("SKIP", levels(render_video.probe(self.plan, self.frames()),
                                     "need/libass"))


class CommandTest(Fixture):

    def test_command_carries_the_frame_rate_and_pattern(self):
        argv = render_video.ffmpeg_command(self.plan, self.tmp / "scene",
                                           self.tmp / "out.mp4")
        self.assertEqual(argv[0], "ffmpeg")
        self.assertIn("-framerate", argv)
        self.assertEqual(argv[argv.index("-framerate") + 1],
                         str(self.plan["canvas"]["fps"]))
        self.assertTrue(any("scene-%06d.png" in part for part in argv))

    def test_command_encodes_for_playback_everywhere(self):
        argv = render_video.ffmpeg_command(self.plan, self.tmp, self.tmp / "out.mp4")
        self.assertEqual(argv[argv.index("-pix_fmt") + 1], "yuv420p")
        self.assertIn("+faststart", argv)

    def test_command_muxes_the_audio_and_stops_at_the_shorter_stream(self):
        argv = render_video.ffmpeg_command(self.plan, self.tmp, self.tmp / "out.mp4")
        self.assertIn("-shortest", argv)
        self.assertIn("-c:a", argv)

    def test_a_silent_plan_asks_for_no_audio_codec(self):
        plan = dict(self.plan, audio={})
        argv = render_video.ffmpeg_command(plan, self.tmp, self.tmp / "out.mp4")
        self.assertNotIn("-c:a", argv)
        self.assertNotIn("-shortest", argv)

    def test_burn_in_goes_through_libass_not_drawtext(self):
        """ADR-035: Pillow cannot shape Thai; libass can."""
        argv = render_video.ffmpeg_command(self.plan, self.tmp, self.tmp / "out.mp4",
                                           sidecar=self.tmp / "demo.ass")
        filters = argv[argv.index("-vf") + 1]
        self.assertIn("subtitles=", filters)
        self.assertNotIn("drawtext", filters)

    def test_a_scaling_profile_adds_a_scale_filter(self):
        timeline = fixtures.timeline()
        plan = videoplan.build(fixtures.animation(timeline), timeline,
                               profile="review-720p", name="demo")
        argv = render_video.ffmpeg_command(plan, self.tmp, self.tmp / "out.mp4")
        self.assertIn("scale=-2:720", argv[argv.index("-vf") + 1])

    def test_frame_numbering_starts_where_the_range_did(self):
        argv = render_video.ffmpeg_command(self.plan, self.tmp, self.tmp / "out.mp4",
                                           start=40)
        self.assertEqual(argv[argv.index("-start_number") + 1], "40")


@unittest.skipIf(Image is None, "Pillow is required")
class GeometryTest(Fixture):

    def test_avatar_sits_on_the_bottom_edge_at_rest(self):
        left, top, width, height = render_video.frame_geometry(
            self.plan, {"scale": 1.0, "x": 0.0, "y": 0.0})
        canvas = self.plan["canvas"]
        self.assertEqual(top + height, canvas["height"])
        self.assertEqual(left + width // 2, canvas["width"] // 2)

    def test_scale_enlarges_about_the_anchor(self):
        rest = render_video.frame_geometry(self.plan, {"scale": 1.0})
        pushed = render_video.frame_geometry(self.plan, {"scale": 1.2})
        self.assertGreater(pushed[3], rest[3])
        self.assertEqual(pushed[1] + pushed[3], rest[1] + rest[3])

    def test_pan_moves_the_avatar_by_a_fraction_of_the_canvas(self):
        canvas = self.plan["canvas"]
        rest = render_video.frame_geometry(self.plan, {"scale": 1.0, "x": 0.0})
        panned = render_video.frame_geometry(self.plan, {"scale": 1.0, "x": 0.1})
        self.assertAlmostEqual(panned[0] - rest[0], canvas["width"] * 0.1, delta=1)

    def test_geometry_is_whole_pixels(self):
        for value in render_video.frame_geometry(self.plan, {"scale": 1.07}):
            self.assertIsInstance(value, int)


@unittest.skipIf(Image is None, "Pillow is required")
class CompositeTest(Fixture):

    def test_scene_frame_is_canvas_sized_and_opaque(self):
        source = Image.new("RGBA", (1024, 1024), (255, 0, 0, 255))
        scene = render_video.compose_frame(self.plan, 0, source)
        canvas = self.plan["canvas"]
        self.assertEqual(scene.size, (canvas["width"], canvas["height"]))
        self.assertEqual(scene.mode, "RGB")

    def test_avatar_lands_where_the_geometry_says(self):
        source = Image.new("RGBA", (1024, 1024), (255, 0, 0, 255))
        scene = render_video.compose_frame(self.plan, 0, source)
        left, top, width, height = render_video.frame_geometry(
            self.plan, self.plan["camera"]["frames"][0])
        self.assertEqual(scene.getpixel((left + width // 2, top + height // 2)),
                         (255, 0, 0))
        self.assertEqual(scene.getpixel((2, 2)), (0, 0, 0))

    def test_transparent_source_shows_the_background(self):
        source = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
        scene = render_video.compose_frame(self.plan, 0, source)
        self.assertEqual(scene.getpixel((self.plan["canvas"]["width"] // 2,
                                         self.plan["canvas"]["height"] - 5)),
                         (0, 0, 0))

    def test_render_scene_writes_one_png_per_frame(self):
        out = render_video.render_scene(self.plan, self.frames(), self.tmp / "scene",
                                        (0, 5))
        self.assertEqual(len(list(out.glob("scene-*.png"))), 5)

    def test_a_missing_avatar_frame_is_an_error(self):
        with self.assertRaises(FileNotFoundError):
            render_video.render_scene(self.plan, self.frames(count=2),
                                      self.tmp / "scene", (0, 5))


class CliTest(Fixture):

    def render(self, plan_path, *args):
        return subprocess.run([sys.executable, str(SCRIPT), str(plan_path), *args],
                              capture_output=True, text=True,
                              env=dict(os.environ, NARRA_REPO=str(self.tmp)))

    def plan_file(self):
        return videoplan.write(self.plan, self.tmp / "demo-video-v1.json")

    def test_check_reports_and_writes_nothing(self):
        result = self.render(self.plan_file(), "--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("CANNOT RENDER", result.stdout)
        self.assertEqual(list(self.tmp.glob("*.mp4")), [])

    def test_check_names_the_missing_frames(self):
        result = self.render(self.plan_file(), "--check")
        self.assertIn("need/frames", result.stdout)

    def test_print_command_runs_no_encoder(self):
        result = self.render(self.plan_file(), "--print-command")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("ffmpeg "))

    def test_an_unreadable_plan_is_an_error(self):
        broken = self.tmp / "broken.json"
        broken.write_text("{not json")
        self.assertEqual(self.render(broken).returncode, 1)

    @unittest.skipIf(Image is None, "Pillow is required")
    def test_scene_only_composites_without_an_encoder(self):
        result = self.render(self.plan_file(), "--scene-only", "--frames",
                             str(self.frames(count=4)), "--range", "0:4",
                             "--scene-dir", str(self.tmp / "scene"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(list((self.tmp / "scene").glob("*.png"))), 4)

    def test_render_refuses_when_requirements_are_missing(self):
        result = self.render(self.plan_file())
        self.assertEqual(result.returncode, 1)
        self.assertIn("nothing was written", result.stdout)


if __name__ == "__main__":
    unittest.main()
