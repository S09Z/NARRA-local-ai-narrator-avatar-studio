#!/usr/bin/env python3
"""Validate a video plan (PHASE 9).

A plan is checked before it is encoded, because everything worth catching is
decidable from the numbers and none of it is worth an encode to discover. Cues that
overlap put two subtitles on screen at once; a cue past the audio is a subtitle over
black; a camera that outruns its source resolution is an upscale; a canvas with an
odd dimension is rejected by the encoder a minute into the render.

Usage:
    validate_video.py <plan.json>
    validate_video.py <plan.json> --strict      warnings become failures
    validate_video.py --all                     everything in metadata/videos

Exit code 0 = valid, 1 = invalid, 2 = usage error.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import camera as camera_lib                           # noqa: E402
import subtitle as subtitle_lib                       # noqa: E402
import videoplan                                      # noqa: E402
from imagecheck import FAIL, PASS, SKIP, WARN, Report  # noqa: E402

REPO = Path(os.environ.get("NARRA_REPO", Path(__file__).resolve().parents[2]))
VIDEO_DIR = REPO / "metadata" / "videos"

TIME_TOLERANCE = 0.002

REQUIRED_FIELDS = ["schema_version", "character", "canvas", "duration", "frame_count",
                   "camera", "subtitles", "layers", "render", "digest"]


def check_structure(payload, report):
    for field in REQUIRED_FIELDS:
        if field not in payload:
            report.add(FAIL, f"field/{field}", "missing")
    if payload.get("schema_version") != videoplan.SCHEMA_VERSION:
        report.add(WARN, "schema/version", f"{payload.get('schema_version')!r}")
    else:
        report.add(PASS, "schema/version", videoplan.SCHEMA_VERSION)

    kinds = [layer.get("kind") for layer in payload.get("layers") or []]
    if "avatar" not in kinds:
        report.add(FAIL, "layers/avatar", "no avatar layer - there is nothing to render")
    else:
        report.add(PASS, "layers/avatar", " < ".join(kinds) or "avatar")


def check_canvas(payload, report):
    canvas = payload.get("canvas") or {}
    width, height, fps = canvas.get("width"), canvas.get("height"), canvas.get("fps")

    if not width or not height or width <= 0 or height <= 0:
        report.add(FAIL, "canvas/size", f"{width}x{height}")
    elif width % 2 or height % 2:
        report.add(FAIL, "canvas/size",
                   f"{width}x{height} has an odd dimension - libx264 rejects that "
                   "under 4:2:0")
    else:
        report.add(PASS, "canvas/size", f"{width}x{height}")

    source_fps = (payload.get("source_animation") or {}).get("fps")
    if not fps or fps <= 0:
        report.add(FAIL, "canvas/fps", f"{fps!r}")
    elif source_fps and fps != source_fps:
        report.add(FAIL, "canvas/fps",
                   f"the canvas is {fps}fps and the frame plan is {source_fps}fps - "
                   "the lip-sync would drift against its own audio")
    else:
        report.add(PASS, "canvas/fps", f"{fps}")

    duration, frames = payload.get("duration"), payload.get("frame_count")
    if fps and duration and frames:
        expected = frames / fps
        if abs(expected - duration) > 1.0 / fps + TIME_TOLERANCE:
            report.add(FAIL, "canvas/duration",
                       f"{frames} frames at {fps}fps is {expected:.3f}s, the plan says "
                       f"{duration}s")
        else:
            report.add(PASS, "canvas/duration", f"{duration}s over {frames} frames")


def check_camera(payload, report):
    track = payload.get("camera") or {}
    frames = track.get("frames") or []
    wanted = payload.get("frame_count")

    if not frames:
        report.add(FAIL, "camera/frames", "no sampled camera frames")
        return
    if wanted and len(frames) != wanted:
        report.add(FAIL, "camera/frames",
                   f"{len(frames)} camera frames for {wanted} video frames")
    else:
        report.add(PASS, "camera/frames", f"{len(frames)}")

    if track.get("authoritative") != "frames":
        report.add(WARN, "camera/authority",
                   "the plan does not mark the sampled frames as authoritative - two "
                   "renderers may ease differently (ADR-032)")

    try:
        supported = set(camera_lib.supported_easings())
        unknown = sorted({keyframe.get("ease") for keyframe in track.get("keyframes", [])
                          if keyframe.get("ease") not in supported})
        if unknown:
            report.add(FAIL, "camera/easing", f"{', '.join(unknown)} not in the vocabulary")
        else:
            report.add(PASS, "camera/easing", track.get("easing_vocabulary", "gsap"))
    except camera_lib.CameraError as error:
        report.add(FAIL, "camera/easing", str(error))

    for level, name, detail in camera_lib.check_limits(
            track, (payload.get("source_animation") or {}).get("camera_class"),
            payload.get("duration")):
        report.add(level, name, detail)


def check_subtitles(payload, report):
    subtitles = payload.get("subtitles") or {}
    cues = subtitles.get("cues") or []
    duration = payload.get("duration")

    if not cues:
        report.add(SKIP, "subtitle/cues", "the plan carries no subtitles")
        return
    report.add(PASS, "subtitle/cues", f"{len(cues)} cue(s), {subtitles.get('format')}")

    try:
        style = subtitle_lib.load_style()
    except subtitle_lib.SubtitleError as error:
        report.add(FAIL, "subtitle/style", str(error))
        return

    layout, reading = style["layout"], style["reading"]

    backwards = [cue for cue in cues if cue["end"] <= cue["start"]]
    if backwards:
        report.add(FAIL, "subtitle/order",
                   f"{len(backwards)} cue(s) end before they start")
    else:
        report.add(PASS, "subtitle/order", "every cue moves forward")

    overlaps = [(a["index"], b["index"]) for a, b in zip(cues, cues[1:])
                if b["start"] < a["end"] - TIME_TOLERANCE]
    if overlaps:
        report.add(FAIL, "subtitle/overlap",
                   f"{len(overlaps)} overlapping pair(s), first {overlaps[0]} - two "
                   "subtitles on screen at once")
    else:
        report.add(PASS, "subtitle/overlap", "no overlap")

    if duration:
        past = [cue["index"] for cue in cues if cue["end"] > duration + TIME_TOLERANCE]
        if past:
            report.add(FAIL, "subtitle/bounds",
                       f"{len(past)} cue(s) run past the {duration}s audio")
        else:
            report.add(PASS, "subtitle/bounds", f"within {duration}s")

    wide = [cue["index"] for cue in cues
            if any(len(line) > layout["max_characters_per_line"]
                   for line in cue.get("lines", []))]
    tall = [cue["index"] for cue in cues
            if len(cue.get("lines", [])) > layout["max_lines"]]
    if wide or tall:
        report.add(FAIL, "subtitle/layout",
                   f"{len(wide)} cue(s) over {layout['max_characters_per_line']} "
                   f"characters, {len(tall)} over {layout['max_lines']} lines")
    else:
        report.add(PASS, "subtitle/layout",
                   f"<= {layout['max_lines']} lines of "
                   f"{layout['max_characters_per_line']}")

    fast = [cue["index"] for cue in cues if cue.get("too_fast")]
    if fast:
        report.add(WARN, "subtitle/reading-speed",
                   f"{len(fast)} cue(s) exceed {reading['characters_per_second']}cps - "
                   "the script is denser than the audio gives time to read")
    else:
        report.add(PASS, "subtitle/reading-speed",
                   f"<= {reading['characters_per_second']}cps")

    short = [cue["index"] for cue in cues if cue.get("too_short")]
    if short:
        report.add(WARN, "subtitle/min-duration",
                   f"{len(short)} cue(s) held under {reading['min_duration_s']}s - too "
                   "brief to read, and there was no room to extend them")
    else:
        report.add(PASS, "subtitle/min-duration", f">= {reading['min_duration_s']}s")

    empty = [cue["index"] for cue in cues if not cue.get("text", "").strip()]
    if empty:
        report.add(FAIL, "subtitle/text", f"{len(empty)} empty cue(s)")

    if subtitles.get("burn_in") and subtitles.get("format") != "ass":
        report.add(FAIL, "subtitle/burn-in",
                   f"burn-in is set but the format is {subtitles.get('format')!r}; "
                   "libass needs .ass (ADR-035)")
    elif subtitles.get("burn_in"):
        report.add(PASS, "subtitle/burn-in", "ass, through libass")


def check_render(payload, report):
    render = payload.get("render") or {}
    try:
        profiles = videoplan.load_profiles()
    except videoplan.VideoPlanError as error:
        report.add(FAIL, "render/profile", str(error))
        return

    if render.get("profile") not in profiles["profiles"]:
        report.add(FAIL, "render/profile", f"{render.get('profile')!r} is not a profile")
    else:
        report.add(PASS, "render/profile", render["profile"])

    engine = render.get("engine")
    entry = profiles["engines"]["available"].get(engine)
    if entry is None:
        report.add(FAIL, "render/engine", f"{engine!r} is not a known engine")
    elif entry["status"] != "implemented":
        report.add(FAIL, "render/engine",
                   f"{engine} is {entry['status']} - {entry.get('blocked_on', '')}")
    else:
        report.add(PASS, "render/engine", engine)

    if render.get("pixel_format") != "yuv420p":
        report.add(WARN, "render/pixel-format",
                   f"{render.get('pixel_format')!r} - anything but yuv420p will not play "
                   "everywhere")
    else:
        report.add(PASS, "render/pixel-format", "yuv420p")


def check_source(payload, report):
    animation = payload.get("source_animation") or {}
    timeline = payload.get("source_timeline") or {}

    if not animation.get("digest"):
        report.add(FAIL, "source/animation", "no frame plan digest - this plan cannot "
                                             "be traced to the lip-sync it renders")
    else:
        report.add(PASS, "source/animation", animation["digest"][:16])

    if timeline.get("timing_source") == "estimated":
        report.add(WARN, "source/timing",
                   "the source timeline is estimated - no audio was measured, so every "
                   "cue and mouth time is a model's guess")
    elif timeline.get("timing_source"):
        report.add(PASS, "source/timing", timeline["timing_source"])

    audio = payload.get("audio") or {}
    if not audio.get("path"):
        report.add(WARN, "source/audio", "no audio - the video would be silent")
    elif audio.get("duration") and payload.get("duration") and \
            abs(audio["duration"] - payload["duration"]) > 0.05:
        report.add(WARN, "source/audio",
                   f"audio is {audio['duration']}s, the plan is {payload['duration']}s")
    else:
        report.add(PASS, "source/audio", str(audio.get("path")))

    if animation.get("mouth_mode") == "viseme-track" and not timeline.get("digest"):
        report.add(WARN, "source/timeline", "no source timeline digest recorded")


def check_digest(payload, report):
    recorded = payload.get("digest")
    if not recorded:
        report.add(FAIL, "lock/digest", "no digest recorded")
        return
    recomputed = videoplan.digest(payload)
    if recomputed != recorded:
        report.add(FAIL, "lock/digest",
                   f"recorded {recorded[:16]}, recomputed {recomputed[:16]} - the file "
                   "was edited after it was generated")
    else:
        report.add(PASS, "lock/digest", recorded[:16])


def validate(path, strict=False):
    report = Report()
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        report.add(FAIL, "file/readable", str(error))
        return report, True

    check_structure(payload, report)
    check_canvas(payload, report)
    check_camera(payload, report)
    check_subtitles(payload, report)
    check_render(payload, report)
    check_source(payload, report)
    check_digest(payload, report)

    failed = report.failed() or (strict and any(level == WARN
                                                for level, _, _ in report.rows))
    return report, failed


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate a video plan (PHASE 9).")
    parser.add_argument("plan", nargs="?")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    if args.all:
        targets = sorted(VIDEO_DIR.glob("*.json"))
        if not targets:
            print(f"no video plans in {VIDEO_DIR}")
            return 0
    elif args.plan:
        targets = [Path(args.plan)]
    else:
        parser.error("give a video plan path or --all")

    worst = 0
    for target in targets:
        report, failed = validate(target, args.strict)
        print(f"\n{target}")
        print(report.render())
        counts = "  ".join(f"{level} {count}"
                           for level, count in sorted(report.counts().items()))
        print(f"  -> {'INVALID' if failed else 'valid'}   {counts}")
        worst = max(worst, 1 if failed else 0)
    return worst


if __name__ == "__main__":
    sys.exit(main())
