#!/usr/bin/env python3
"""Assemble a video plan from a PHASE 8 frame plan (PHASE 9).

animation.json (+ its PHASE 7 timeline) -> metadata/videos/<name>-video-v1.json

Writes a plan and a subtitle sidecar. It renders nothing: the plan is the artefact
that gets reviewed, corrected, and only then encoded (ADR-032). The timeline is
found by matching the digest the frame plan recorded, so a plan can never be built
against a different sentence than the one it was animated from.

Usage:
    build_video.py metadata/animations/greeting-animation-v1.json
    build_video.py <animation> --move slow-push --profile review-720p
    build_video.py <animation> --timeline <timeline.json> --canvas 1080x1080
    build_video.py <animation> --no-subtitles
    build_video.py <animation> --report          print the plan and write nothing

Exit code 0 = plan written, 1 = cannot build, 2 = usage error.
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

REPO = Path(os.environ.get("NARRA_REPO", Path(__file__).resolve().parents[2]))
TIMELINE_DIR = REPO / "metadata" / "timelines"
VIDEO_DIR = REPO / "metadata" / "videos"
SIDECAR_DIR = REPO / "assets" / "video"


def find_timeline(animation):
    """The timeline this frame plan was built from, by digest, not by filename."""
    wanted = (animation.get("source_timeline") or {}).get("digest")
    if not wanted or not TIMELINE_DIR.is_dir():
        return None, wanted
    for path in sorted(TIMELINE_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("digest") == wanted or wanted.startswith(
                str(payload.get("digest") or "\0")):
            return payload, wanted
    return None, wanted


def parse_canvas(value):
    if not value:
        return None
    try:
        width, _, height = value.partition("x")
        return {"width": int(width), "height": int(height)}
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(f"canvas {value!r} is not WIDTHxHEIGHT")


def sidecar_path(name, fmt):
    return SIDECAR_DIR / f"{name}.{'ass' if fmt == 'ass' else fmt}"


def write_sidecar(plan, name):
    """The reviewable subtitle file. Its own artefact, on purpose (ADR-035)."""
    cues = plan["subtitles"]["cues"]
    if not cues:
        return None
    fmt = plan["subtitles"]["format"]
    if fmt == "srt":
        body = subtitle_lib.to_srt(cues)
    elif fmt == "ass":
        body = subtitle_lib.to_ass(cues, canvas=plan["canvas"])
    else:
        body = json.dumps(cues, ensure_ascii=False, indent=2) + "\n"
    path = sidecar_path(name, fmt)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def report(plan, timeline_found, sidecar):
    lines = [""]
    def row(label, value):
        lines.append(f"  {label:14}{value}")

    canvas = plan["canvas"]
    row("name", plan["name"])
    row("canvas", f"{canvas['width']}x{canvas['height']} @ {canvas['fps']}fps")
    row("frames", f"{plan['frame_count']} over {plan['duration']}s")
    row("camera", f"{plan['camera']['move']} "
                  f"({len(plan['camera']['keyframes'])} keyframe(s))")
    row("pose", f"{plan['source_animation']['pose']} / "
                f"{plan['source_animation']['camera_class']}")
    subtitles = plan["subtitles"]
    row("subtitles", f"{subtitles['cue_count']} cue(s), {subtitles['format']}"
                     + (", burned in" if subtitles["burn_in"] else ", sidecar"))
    row("profile", f"{plan['render']['profile']} -> {plan['render']['engine']}")
    row("digest", plan["digest"][:16])
    if sidecar:
        row("sidecar", sidecar)

    findings = camera_lib.check_limits(plan["camera"],
                                       plan["source_animation"].get("camera_class"),
                                       plan.get("duration"))
    for level, name, detail in findings:
        if level != "PASS":
            lines.append(f"  {level.lower()}: {name} - {detail}")

    fast = [cue for cue in subtitles["cues"] if cue.get("too_fast")]
    if fast:
        lines.append(f"  warn: {len(fast)} cue(s) run faster than the configured reading "
                     "speed - the script is denser than the audio allows")
    short = [cue for cue in subtitles["cues"] if cue.get("too_short")]
    if short:
        lines.append(f"  warn: {len(short)} cue(s) could not be held for the minimum "
                     "duration without colliding with the next one")
    if not timeline_found:
        lines.append("  warn: no matching timeline found - built without subtitles")
    if plan["source_timeline"].get("timing_source") == "estimated":
        lines.append("  warn: the source timeline is estimated - no audio was measured, "
                     "so every cue time is a model's guess")
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Assemble a video plan from a frame plan (PHASE 9).")
    parser.add_argument("animation", help="PHASE 8 animation JSON")
    parser.add_argument("--timeline", help="PHASE 7 timeline; found by digest if omitted")
    parser.add_argument("--move", help="camera move name from docs/video/camera-model.json")
    parser.add_argument("--profile", help="render profile")
    parser.add_argument("--canvas", help="WIDTHxHEIGHT, e.g. 1080x1080")
    parser.add_argument("--no-subtitles", action="store_false", dest="subtitles")
    parser.add_argument("--subtitle-format", choices=["srt", "ass", "json"])
    parser.add_argument("--burn-in", action="store_true",
                        help="mark subtitles for burn-in (render_video.py checks shaping)")
    parser.add_argument("--out", help="video plan path")
    parser.add_argument("--name", help="basename for the plan and its sidecar")
    parser.add_argument("--report", action="store_true", help="print and write nothing")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    try:
        animation = json.loads(Path(args.animation).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"cannot read {args.animation}: {error}", file=sys.stderr)
        return 1

    if args.timeline:
        try:
            timeline = json.loads(Path(args.timeline).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"cannot read {args.timeline}: {error}", file=sys.stderr)
            return 1
    else:
        timeline, wanted = find_timeline(animation)
        if timeline is None and args.subtitles:
            print(f"no timeline in {TIMELINE_DIR} matches digest "
                  f"{(wanted or '?')[:16]} - pass --timeline, or --no-subtitles",
                  file=sys.stderr)
            return 1

    name = args.name or Path(args.animation).stem.replace("-animation-v1", "")
    try:
        plan = videoplan.build(
            animation, timeline, move=args.move, profile=args.profile,
            canvas=parse_canvas(args.canvas), subtitles=args.subtitles,
            subtitle_format=args.subtitle_format, burn_in=args.burn_in, name=name)
    except (videoplan.VideoPlanError, camera_lib.CameraError,
            subtitle_lib.SubtitleError) as error:
        print(f"cannot build a video plan: {error}", file=sys.stderr)
        return 1

    if args.report:
        if args.as_json:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
        else:
            print(report(plan, timeline is not None, None))
        return 0

    out = Path(args.out) if args.out else VIDEO_DIR / f"{name}-video-v1.json"
    videoplan.write(plan, out)
    sidecar = write_sidecar(plan, name) if args.subtitles else None

    if args.as_json:
        print(json.dumps({"plan": str(out),
                          "sidecar": str(sidecar) if sidecar else None,
                          "digest": plan["digest"]}, ensure_ascii=False, indent=2))
    else:
        print(f"\nwrote {out}")
        print(report(plan, timeline is not None,
                     sidecar.relative_to(REPO) if sidecar else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
