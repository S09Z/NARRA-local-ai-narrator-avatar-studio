#!/usr/bin/env python3
"""Render a video plan to MP4 (PHASE 9).

video plan + PHASE 8 frames + audio -> assets/video/<name>.mp4

Two stages, deliberately separable. Pillow composites each scene frame: background,
b-roll, and the avatar under the camera transform. ffmpeg encodes those frames,
muxes the audio, and - when the plan asks for burned-in subtitles - draws the text
itself through libass.

Text is never drawn by Pillow. Pillow shapes complex scripts only when built against
Raqm, and without it Thai tone marks are placed by glyph advance and land beside the
consonant instead of above it. libass shapes through HarfBuzz unconditionally, so
the subtitle path goes there and only there (ADR-035).

Usage:
    render_video.py <plan.json> --check          what is missing, decodes nothing
    render_video.py <plan.json>
    render_video.py <plan.json> --frames assets/frames/greeting
    render_video.py <plan.json> --scene-only     composite frames, do not encode
    render_video.py <plan.json> --range 0:50
    render_video.py <plan.json> --print-command  the ffmpeg call, without running it

Exit code 0 = done, 1 = cannot render, 2 = usage error.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "validation"))
import videoplan                                      # noqa: E402
from imagecheck import FAIL, PASS, SKIP, WARN, Report  # noqa: E402

REPO = Path(os.environ.get("NARRA_REPO", Path(__file__).resolve().parents[2]))
FRAME_DIR = REPO / "assets" / "frames"
VIDEO_DIR = REPO / "assets" / "video"

SCENE_PATTERN = "scene-%06d.png"


def _pillow():
    try:
        from PIL import Image
        return Image
    except ImportError:
        return None


# --- requirements ----------------------------------------------------------------

def ffmpeg_has_libass():
    binary = shutil.which("ffmpeg")
    if not binary:
        return False
    try:
        done = subprocess.run([binary, "-version"], capture_output=True, text=True,
                              timeout=20)
    except (OSError, subprocess.SubprocessError):
        return False
    return "--enable-libass" in done.stdout


def frames_dir_for(plan, override=None):
    return Path(override) if override else FRAME_DIR / plan.get("name", "video")


def probe(plan, frames_dir=None, report=None):
    """What a render needs, and whether it is here. Decodes nothing."""
    report = report or Report()
    frames = frames_dir_for(plan, frames_dir)

    if _pillow() is None:
        report.add(FAIL, "need/pillow", "Pillow is not installed - `make install`")
    else:
        report.add(PASS, "need/pillow", "present")

    wanted = plan.get("frame_count") or 0
    found = sorted(frames.glob("frame-*.png")) if frames.is_dir() else []
    if not found:
        report.add(FAIL, "need/frames",
                   f"no PHASE 8 frames in {frames} - render them with "
                   "scripts/animation/render_frames.py, which needs the image library")
    elif len(found) < wanted:
        report.add(FAIL, "need/frames",
                   f"{len(found)} frame(s) in {frames}, the plan is {wanted}")
    else:
        report.add(PASS, "need/frames", f"{len(found)} in {frames}")

    audio = (plan.get("audio") or {}).get("path")
    if not audio:
        report.add(WARN, "need/audio", "the plan records no audio - video will be silent")
    elif not Path(audio).exists():
        report.add(FAIL, "need/audio", f"{audio} is missing")
    else:
        report.add(PASS, "need/audio", audio)

    if shutil.which("ffmpeg"):
        report.add(PASS, "need/ffmpeg", shutil.which("ffmpeg"))
    else:
        report.add(FAIL, "need/ffmpeg",
                   "ffmpeg is not on PATH - it encodes, muxes the audio, and draws "
                   "burned-in subtitles")

    if (plan.get("subtitles") or {}).get("burn_in"):
        if not shutil.which("ffmpeg"):
            report.add(SKIP, "need/libass", "no ffmpeg to ask")
        elif ffmpeg_has_libass():
            report.add(PASS, "need/libass", "ffmpeg is built with libass")
        else:
            report.add(FAIL, "need/libass",
                       "this ffmpeg has no libass, so it cannot shape Thai - keep the "
                       "sidecar instead of burning in")
        sidecar = subtitle_sidecar(plan)
        if sidecar and sidecar.exists():
            report.add(PASS, "need/sidecar", str(sidecar))
        else:
            report.add(FAIL, "need/sidecar",
                       f"burn-in needs an .ass sidecar; {sidecar} is missing - rebuild "
                       "the plan with --subtitle-format ass")
    else:
        report.add(SKIP, "need/libass", "subtitles ship as a sidecar, not burned in")

    return report


def subtitle_sidecar(plan):
    """Burn-in reads .ass and only .ass - libass is what shapes the Thai (ADR-035)."""
    return VIDEO_DIR / f"{plan.get('name', 'video')}.ass"


# --- compositing -----------------------------------------------------------------

def frame_geometry(plan, camera_frame):
    """Where the avatar lands on the canvas for one frame, in whole pixels."""
    canvas = plan["canvas"]
    avatar = next(layer for layer in plan["layers"] if layer["kind"] == "avatar")
    scale = camera_frame.get("scale", 1.0)

    height = canvas["height"] * avatar["height_fraction"] * scale
    width = height                                     # assets are 1:1 (ASSET_SPEC 2)
    left = (canvas["width"] - width) / 2 + camera_frame.get("x", 0.0) * canvas["width"]
    if avatar["anchor"] == "bottom-center":
        top = canvas["height"] - height
    else:
        top = (canvas["height"] - height) / 2
    top += camera_frame.get("y", 0.0) * canvas["height"]
    return (int(round(left)), int(round(top)),
            max(1, int(round(width))), max(1, int(round(height))))


def compose_frame(plan, index, source, image_module=None):
    """One scene frame: background, then the avatar under the camera transform."""
    Image = image_module or _pillow()
    if Image is None:
        raise RuntimeError("Pillow is required to composite scene frames")

    canvas = plan["canvas"]
    scene = Image.new("RGBA", (canvas["width"], canvas["height"]),
                      canvas.get("background", "#000000"))

    camera_frames = (plan.get("camera") or {}).get("frames") or []
    camera_frame = camera_frames[min(index, len(camera_frames) - 1)] if camera_frames \
        else {"scale": 1.0, "x": 0.0, "y": 0.0}

    left, top, width, height = frame_geometry(plan, camera_frame)
    avatar = source if isinstance(source, Image.Image) else Image.open(source)
    if avatar.mode != "RGBA":
        avatar = avatar.convert("RGBA")
    avatar = avatar.resize((width, height), Image.LANCZOS)
    scene.alpha_composite(avatar, (left, top))
    return scene.convert("RGB")


def render_scene(plan, frames_dir=None, out_dir=None, frame_range=None,
                 image_module=None):
    """Composite every scene frame to PNG. Returns the directory written."""
    frames = frames_dir_for(plan, frames_dir)
    out = Path(out_dir) if out_dir else VIDEO_DIR / f"{plan.get('name', 'video')}-scene"
    out.mkdir(parents=True, exist_ok=True)

    start, stop = frame_range or (0, plan["frame_count"])
    for index in range(start, min(stop, plan["frame_count"])):
        source = frames / f"frame-{index:06d}.png"
        if not source.exists():
            raise FileNotFoundError(f"missing avatar frame {source}")
        scene = compose_frame(plan, index, source, image_module)
        scene.save(out / (SCENE_PATTERN % index))
    return out


# --- encoding --------------------------------------------------------------------

def ffmpeg_command(plan, scene_dir, out_path, sidecar=None, start=0):
    """The exact ffmpeg call. A pure function, so it is testable without ffmpeg."""
    render = plan.get("render") or {}
    canvas = plan["canvas"]
    audio = (plan.get("audio") or {}).get("path")

    argv = ["ffmpeg", "-y",
            "-framerate", str(canvas["fps"]),
            "-start_number", str(start),
            "-i", str(Path(scene_dir) / SCENE_PATTERN)]
    if audio:
        argv += ["-i", str(audio)]

    filters = []
    if sidecar:
        # libass, not drawtext: drawtext cannot shape Thai either.
        filters.append(f"subtitles={sidecar}")
    if render.get("scale_height"):
        filters.append(f"scale=-2:{render['scale_height']}")
    if filters:
        argv += ["-vf", ",".join(filters)]

    argv += ["-c:v", render.get("video_codec", "libx264"),
             "-crf", str(render.get("crf", 18)),
             "-preset", render.get("preset", "slow"),
             "-pix_fmt", render.get("pixel_format", "yuv420p")]
    if audio:
        argv += ["-c:a", render.get("audio_codec", "aac"),
                 "-b:a", render.get("audio_bitrate", "192k"), "-shortest"]
    if render.get("faststart"):
        argv += ["-movflags", "+faststart"]
    argv.append(str(out_path))
    return argv


def encode(plan, scene_dir, out_path, sidecar=None, start=0):
    command = ffmpeg_command(plan, scene_dir, out_path, sidecar, start)
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode != 0:
        tail = "\n".join(done.stderr.strip().splitlines()[-6:])
        raise RuntimeError(f"ffmpeg failed:\n{tail}")
    return Path(out_path)


def parse_range(value):
    if not value:
        return None
    start, _, stop = value.partition(":")
    return (int(start or 0), int(stop) if stop else None)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render a video plan (PHASE 9).")
    parser.add_argument("plan", help="video plan JSON from build_video.py")
    parser.add_argument("--frames", help="PHASE 8 frame directory")
    parser.add_argument("--out", help="output MP4 path")
    parser.add_argument("--scene-dir", help="where composited scene frames go")
    parser.add_argument("--range", dest="frame_range", help="START:STOP frames")
    parser.add_argument("--check", action="store_true",
                        help="report what a render needs, and decode nothing")
    parser.add_argument("--scene-only", action="store_true",
                        help="composite scene frames and stop before encoding")
    parser.add_argument("--print-command", action="store_true",
                        help="print the ffmpeg call without running it")
    parser.add_argument("--keep-scene", action="store_true",
                        help="keep the composited PNGs after encoding")
    args = parser.parse_args(argv)

    try:
        plan = videoplan.load(args.plan)
    except videoplan.VideoPlanError as error:
        print(error, file=sys.stderr)
        return 1

    name = plan.get("name", "video")
    out_path = Path(args.out) if args.out else VIDEO_DIR / f"{name}.mp4"
    scene_dir = Path(args.scene_dir) if args.scene_dir else VIDEO_DIR / f"{name}-scene"
    sidecar = subtitle_sidecar(plan) if (plan.get("subtitles") or {}).get("burn_in") \
        else None

    if args.print_command:
        print(" ".join(ffmpeg_command(plan, scene_dir, out_path, sidecar)))
        return 0

    report = probe(plan, args.frames)
    if args.check:
        print(f"\n{args.plan}")
        print(report.render())
        blocked = report.failed()
        print(f"  -> {'CANNOT RENDER' if blocked else 'ready to render'}")
        return 1 if blocked else 0

    if report.failed() and not args.scene_only:
        print(f"\n{args.plan}")
        print(report.render())
        print("  -> CANNOT RENDER; nothing was written")
        return 1

    frame_range = parse_range(args.frame_range)
    if frame_range and frame_range[1] is None:
        frame_range = (frame_range[0], plan["frame_count"])

    try:
        written = render_scene(plan, args.frames, scene_dir, frame_range)
    except (FileNotFoundError, RuntimeError) as error:
        print(f"cannot composite: {error}", file=sys.stderr)
        return 1
    print(f"composited scene frames -> {written}")

    if args.scene_only:
        return 0

    try:
        encode(plan, written, out_path, sidecar, frame_range[0] if frame_range else 0)
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    if not args.keep_scene:
        shutil.rmtree(written, ignore_errors=True)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
