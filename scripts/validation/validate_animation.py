#!/usr/bin/env python3
"""Validate a lip-sync frame plan (PHASE 8).

A frame plan is what PHASE 9 renders. Everything checked here is something that would
otherwise appear as a wrong-looking mouth rather than as an error: weights that do not
sum to one leave a frame partly undefined, an open-mouth expression under a viseme track
renders two mouths, a bilabial that never closes reads as a different consonant, and a
shape held for one frame is the flicker mapping.md section 6 forbids.

Usage:
    validate_animation.py <animation.json>
    validate_animation.py <animation.json> --strict     warnings become failures
    validate_animation.py --all                         everything in metadata/animations

Exit code 0 = valid, 1 = invalid, 2 = usage error.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import animation as animation_lib                     # noqa: E402
import canon                                          # noqa: E402
from imagecheck import FAIL, PASS, SKIP, WARN, Report  # noqa: E402

REPO = Path(os.environ.get("NARRA_REPO", Path(__file__).resolve().parents[2]))
ANIMATION_DIR = REPO / "metadata" / "animations"

WEIGHT_TOLERANCE = 0.005
TIME_TOLERANCE = 0.002

REQUIRED_FIELDS = ["schema_version", "character", "state", "mouth_mode", "fps",
                   "duration", "frame_count", "tracks", "coarticulation", "digest"]


def check_structure(payload, report):
    for field in REQUIRED_FIELDS:
        if field not in payload:
            report.add(FAIL, f"field/{field}", "missing")
    if payload.get("schema_version") != animation_lib.SCHEMA_VERSION:
        report.add(WARN, "schema/version", f"{payload.get('schema_version')!r}")
    else:
        report.add(PASS, "schema/version", animation_lib.SCHEMA_VERSION)

    fps = payload.get("fps")
    if not isinstance(fps, int) or fps <= 0:
        report.add(FAIL, "fps", f"{fps!r} is not a positive integer")
    else:
        report.add(PASS, "fps", str(fps))


def check_frames(payload, report):
    frames = (payload.get("tracks") or {}).get("mouth") or []
    fps = payload.get("fps") or 0
    if not frames:
        report.add(FAIL, "frames/present", "no mouth frames")
        return
    report.add(PASS, "frames/present", f"{len(frames)} frames")

    if payload.get("frame_count") != len(frames):
        report.add(FAIL, "frames/count",
                   f"frame_count says {payload.get('frame_count')}, track has "
                   f"{len(frames)}")
    else:
        report.add(PASS, "frames/count", str(len(frames)))

    out_of_order = [index for index, frame in enumerate(frames)
                    if frame.get("frame") != index]
    if out_of_order:
        report.add(FAIL, "frames/sequential",
                   f"{len(out_of_order)} frame(s) out of order, first at index "
                   f"{out_of_order[0]}")
    else:
        report.add(PASS, "frames/sequential", "0..n with no gaps")

    if fps:
        drifted = [frame for frame in frames
                   if abs(frame.get("time", 0) - frame["frame"] / fps) > TIME_TOLERANCE]
        if drifted:
            report.add(FAIL, "frames/time",
                       f"{len(drifted)} frame time(s) disagree with frame/fps")
        else:
            report.add(PASS, "frames/time", f"consistent with {fps}fps")


def check_weights(payload, report):
    frames = (payload.get("tracks") or {}).get("mouth") or []
    maximum = (payload.get("coarticulation") or {}).get("max_simultaneous_layers")
    if maximum is None:
        maximum = animation_lib.load_coarticulation()["max_simultaneous_layers"]

    unnormalised, overfull, duplicated, uncanonical = [], [], [], set()
    for frame in frames:
        layers = frame.get("layers") or []
        if not layers:
            continue
        total = sum(layer.get("weight", 0) for layer in layers)
        if abs(total - 1.0) > WEIGHT_TOLERANCE:
            unnormalised.append((frame["frame"], round(total, 4)))
        if len(layers) > maximum:
            overfull.append(frame["frame"])
        names = [layer.get("viseme") for layer in layers]
        if len(set(names)) != len(names):
            duplicated.append(frame["frame"])
        for name in names:
            if name not in canon.VISEMES:
                uncanonical.add(name)

    if unnormalised:
        report.add(FAIL, "weights/normalised",
                   f"{len(unnormalised)} frame(s) do not sum to 1.0, first frame "
                   f"{unnormalised[0][0]} sums to {unnormalised[0][1]}")
    else:
        report.add(PASS, "weights/normalised", "every frame sums to 1.0")

    if overfull:
        report.add(FAIL, "weights/layer-count",
                   f"{len(overfull)} frame(s) exceed {maximum} layers - three shapes "
                   "blend to mud")
    else:
        report.add(PASS, "weights/layer-count", f"at most {maximum} layers")

    if duplicated:
        report.add(FAIL, "weights/distinct",
                   f"{len(duplicated)} frame(s) carry the same viseme twice - a shape "
                   "cannot crossfade with itself")
    else:
        report.add(PASS, "weights/distinct", "one layer per shape")

    if uncanonical:
        report.add(FAIL, "viseme/canonical",
                   f"{', '.join(sorted(uncanonical))} not in the canonical set")
    elif frames:
        report.add(PASS, "viseme/canonical", "all canonical")


def check_flicker(payload, report):
    """mapping.md section 6, restated in frames - what actually reaches the eye."""
    frames = (payload.get("tracks") or {}).get("mouth") or []
    minimum = (payload.get("coarticulation") or {}).get("min_frames_on_screen")
    if not minimum or not frames:
        report.add(SKIP, "frames/min-hold", "no minimum recorded")
        return

    primaries = []
    for frame in frames:
        layers = frame.get("layers") or []
        primaries.append(max(layers, key=lambda layer: layer["weight"])["viseme"]
                         if layers else None)

    runs, current, length = [], object(), 0
    for primary in primaries:
        if primary == current:
            length += 1
            continue
        if length:
            runs.append((current, length))
        current, length = primary, 1
    runs.append((current, length))

    interior = runs[1:-1] if len(runs) > 2 else []
    short = [(name, length) for name, length in interior if length < minimum]
    if short:
        report.add(FAIL, "frames/min-hold",
                   f"{len(short)} shape(s) held under {minimum} frames, first "
                   f"{short[0][0]} for {short[0][1]} - reads as a flicker")
    else:
        report.add(PASS, "frames/min-hold", f"every hold >= {minimum} frames")


def check_closures(payload, report):
    """CLAUDE.md - MBP must be visually distinct from REST, so it has to actually close."""
    meta = payload.get("mouth_meta") or {}
    unresolved = [entry for entry in meta.get("closures", [])
                  if not entry.get("resolved")]
    starved = [entry for entry in meta.get("extended", []) if not entry.get("given")]

    if unresolved:
        report.add(FAIL, "closure/complete",
                   f"{len(unresolved)} closure(s) never reach full weight - a bilabial "
                   "that does not close reads as a different consonant")
    else:
        report.add(PASS, "closure/complete", "every closure reaches full weight")

    if starved:
        report.add(FAIL, "closure/visible",
                   f"{len(starved)} closure(s) too brief to show and no neighbour long "
                   f"enough to donate - {starved[0].get('reason')}")
    else:
        report.add(PASS, "closure/visible", "no closure was dropped")

    if payload.get("mouth_mode") == "viseme-track":
        frames = (payload.get("tracks") or {}).get("mouth") or []
        closures = set(animation_lib.load_coarticulation()["closure_visemes"])
        present = {layer["viseme"] for frame in frames for layer in frame["layers"]}
        if closures & present:
            full = {name for frame in frames for layer in frame["layers"]
                    if layer["viseme"] in closures and layer["weight"] >= 0.999
                    for name in [layer["viseme"]]}
            missing = (closures & present) - full
            if missing:
                report.add(FAIL, "closure/full-weight",
                           f"{', '.join(sorted(missing))} never reaches weight 1.0 on "
                           "any frame")
            else:
                report.add(PASS, "closure/full-weight",
                           f"{', '.join(sorted(full))} fully closed")


def check_expression(payload, report):
    segments = (payload.get("tracks") or {}).get("expression") or []
    if not segments:
        report.add(FAIL, "expression/present", "no expression track")
        return

    unknown = sorted({segment["expression"] for segment in segments
                      if canon.index_of("expression", segment["expression"]) is None})
    if unknown:
        report.add(FAIL, "expression/canonical", f"{', '.join(unknown)}")
    else:
        report.add(PASS, "expression/canonical",
                   f"{len(set(s['expression'] for s in segments))} distinct")

    gaps = [(a["end"], b["start"]) for a, b in zip(segments, segments[1:])
            if abs(b["start"] - a["end"]) > TIME_TOLERANCE]
    if gaps:
        report.add(FAIL, "expression/contiguous",
                   f"{len(gaps)} gap(s), first {gaps[0][0]}->{gaps[0][1]} - the face "
                   "would be undefined there")
    else:
        report.add(PASS, "expression/contiguous", "covers the duration")

    duration = payload.get("duration")
    if duration and abs(segments[-1]["end"] - duration) > TIME_TOLERANCE:
        report.add(FAIL, "expression/duration",
                   f"track ends at {segments[-1]['end']}, animation is {duration}s")
    else:
        report.add(PASS, "expression/duration", f"{duration}s")

    if payload.get("mouth_mode") == "viseme-track":
        conflicts = sorted({segment["expression"] for segment in segments
                            if segment["expression"] in canon.OPEN_MOUTH_EXPRESSIONS})
        if conflicts:
            report.add(FAIL, "expression/open-mouth",
                       f"{', '.join(conflicts)} has an open mouth and cannot host a "
                       "viseme track (ADR-012) - it would render two mouths")
        else:
            report.add(PASS, "expression/open-mouth", "no open-mouth conflict")
    else:
        report.add(SKIP, "expression/open-mouth",
                   "mouth is static - the expression carries its own mouth")


def check_secondary(payload, report):
    tracks = payload.get("tracks") or {}
    duration = payload.get("duration") or 0
    blinks = tracks.get("blink") or []
    stray = [blink for blink in blinks
             if blink["start"] < 0 or blink["end"] > duration + TIME_TOLERANCE]
    if stray:
        report.add(FAIL, "secondary/blink", f"{len(stray)} blink(s) outside the duration")
    else:
        report.add(PASS, "secondary/blink", f"{len(blinks)} blink(s)")

    frames = len(tracks.get("mouth") or [])
    breath = (tracks.get("breath") or {}).get("values") or []
    if breath and len(breath) != frames:
        report.add(FAIL, "secondary/breath",
                   f"{len(breath)} breath samples for {frames} frames")
    elif breath:
        report.add(PASS, "secondary/breath", f"{len(breath)} samples")
    else:
        report.add(SKIP, "secondary/breath", "no breath track")


def check_source(payload, report):
    source = payload.get("source_timeline") or {}
    if not source.get("digest"):
        report.add(WARN, "source/timeline", "no source timeline digest recorded")
    else:
        report.add(PASS, "source/timeline", source["digest"][:16])
    if source.get("timing_source") == "estimated":
        report.add(WARN, "source/timing",
                   "the source timeline is estimated - no audio was measured, so these "
                   "frame times are a model's guess")
    elif source.get("timing_source"):
        report.add(PASS, "source/timing", source["timing_source"])


def check_digest(payload, report):
    recorded = payload.get("digest")
    if not recorded:
        report.add(FAIL, "lock/digest", "no digest recorded")
        return
    recomputed = animation_lib.digest(payload)
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
    check_frames(payload, report)
    check_weights(payload, report)
    check_flicker(payload, report)
    check_closures(payload, report)
    check_expression(payload, report)
    check_secondary(payload, report)
    check_source(payload, report)
    check_digest(payload, report)

    failed = report.failed() or (strict and any(level == WARN
                                                for level, _, _ in report.rows))
    return report, failed


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate a frame plan (PHASE 8).")
    parser.add_argument("animation", nargs="?")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    if args.all:
        targets = sorted(ANIMATION_DIR.glob("*.json"))
        if not targets:
            print(f"no animations in {ANIMATION_DIR}")
            return 0
    elif args.animation:
        targets = [Path(args.animation)]
    else:
        parser.error("give an animation path or --all")

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
