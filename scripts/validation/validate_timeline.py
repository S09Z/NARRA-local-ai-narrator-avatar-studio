#!/usr/bin/env python3
"""Validate a viseme timeline (PHASE 7.4).

A timeline is an instruction sheet for PHASE 8. Everything checked here is something
that would otherwise surface as a broken animation rather than as an error: a gap
between events leaves the mouth undefined, a viseme outside the canonical set names an
asset that will never exist, and a timeline whose digest no longer matches its contents
has been edited by hand and is no longer reproducible.

The mapping being unreviewed by a Thai speaker (PHASE 4.2) is a WARN, not a FAIL. It is
a real limitation and it should be visible on every run, but it does not make the file
malformed.

Usage:
    validate_timeline.py <timeline.json>
    validate_timeline.py <timeline.json> --strict     warnings become failures
    validate_timeline.py --all                        every timeline in metadata/

Exit code 0 = valid, 1 = invalid, 2 = usage error.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import audioinfo                                      # noqa: E402
import canon                                          # noqa: E402
import timeline as timeline_lib                       # noqa: E402
from imagecheck import FAIL, PASS, SKIP, WARN, Report  # noqa: E402

REPO = Path(os.environ.get("NARRA_REPO", Path(__file__).resolve().parents[2]))
TIMELINE_DIR = REPO / "metadata" / "timelines"

TOLERANCE = 0.002            # events are stored to 3dp; this is one rounding step
COVERAGE_FLOOR = 0.95
TIMING_SOURCES = {timeline_lib.ESTIMATED, timeline_lib.FITTED, timeline_lib.ALIGNED}

REQUIRED_FIELDS = ["schema_version", "character", "language", "text", "duration",
                   "timing_source", "idle_viseme", "g2p", "viseme_map",
                   "duration_model", "events", "digest"]


def check_structure(payload, report):
    for field in REQUIRED_FIELDS:
        if field not in payload:
            report.add(FAIL, f"field/{field}", "missing")
    if payload.get("schema_version") != timeline_lib.SCHEMA_VERSION:
        report.add(WARN, "schema/version",
                   f"{payload.get('schema_version')!r}, this tool knows "
                   f"{timeline_lib.SCHEMA_VERSION!r}")
    else:
        report.add(PASS, "schema/version", timeline_lib.SCHEMA_VERSION)

    source = payload.get("timing_source")
    if source not in TIMING_SOURCES:
        report.add(FAIL, "timing/source",
                   f"{source!r} is not one of {', '.join(sorted(TIMING_SOURCES))}")
    elif source == timeline_lib.ESTIMATED:
        report.add(WARN, "timing/source",
                   "estimated - no audio was measured, these times are a model's guess")
    else:
        report.add(PASS, "timing/source", source)


def check_events(payload, report):
    events = payload.get("events") or []
    if not events:
        report.add(FAIL, "events/present", "no events")
        return

    report.add(PASS, "events/present", f"{len(events)} events")

    if abs(events[0]["start"]) > TOLERANCE:
        report.add(FAIL, "events/start", f"first event starts at {events[0]['start']}, "
                                         "expected 0")
    else:
        report.add(PASS, "events/start", "0.0")

    gaps = []
    backwards = []
    for previous, current in zip(events, events[1:]):
        if abs(current["start"] - previous["end"]) > TOLERANCE:
            gaps.append((previous["end"], current["start"]))
        if current["start"] < previous["start"]:
            backwards.append(current["start"])
    if gaps:
        report.add(FAIL, "events/contiguous",
                   f"{len(gaps)} gap(s) or overlap(s), first at {gaps[0][0]}->{gaps[0][1]} "
                   "- the mouth would be undefined there")
    else:
        report.add(PASS, "events/contiguous", "no gaps or overlaps")
    if backwards:
        report.add(FAIL, "events/monotonic", f"{len(backwards)} event(s) go backwards")
    else:
        report.add(PASS, "events/monotonic", "start times increase")

    empty = [index for index, event in enumerate(events)
             if event["end"] - event["start"] <= 0]
    if empty:
        report.add(FAIL, "events/positive", f"{len(empty)} zero-length event(s)")
    else:
        report.add(PASS, "events/positive", "all events have length")

    duration = payload.get("duration")
    if duration is not None and abs(events[-1]["end"] - duration) > TOLERANCE:
        report.add(FAIL, "events/duration",
                   f"last event ends at {events[-1]['end']}, duration says {duration}")
    else:
        report.add(PASS, "events/duration", f"{duration}s")


def check_visemes(payload, report):
    events = payload.get("events") or []
    unknown = sorted({event["viseme"] for event in events
                      if event["viseme"] not in canon.VISEMES})
    if unknown:
        report.add(FAIL, "viseme/canonical",
                   f"{', '.join(unknown)} not in the canonical set - "
                   "no such asset can exist")
    elif events:
        report.add(PASS, "viseme/canonical",
                   f"{len(set(e['viseme'] for e in events))} distinct, all canonical")

    idle = payload.get("idle_viseme")
    if idle and canon.index_of("viseme", idle) is None:
        report.add(FAIL, "viseme/idle", f"{idle!r} is not a canonical viseme")
    elif idle:
        report.add(PASS, "viseme/idle", idle)

    repeats = [previous["viseme"] for previous, current in zip(events, events[1:])
               if previous["viseme"] == current["viseme"]]
    if repeats:
        report.add(FAIL, "viseme/no-repeats",
                   f"{len(repeats)} adjacent duplicate(s), first {repeats[0]!r} - "
                   "one hold was emitted as two events")
    elif events:
        report.add(PASS, "viseme/no-repeats", "no adjacent duplicates")


def check_flicker(payload, report):
    """mapping.md section 6 - a viseme too short to read is a defect, not a detail."""
    minimum = (payload.get("duration_model") or {}).get("min_viseme_duration_s")
    if not minimum:
        report.add(SKIP, "viseme/min-duration", "the timeline records no minimum")
        return
    short = [event for event in payload.get("events") or []
             if (event["end"] - event["start"]) + TOLERANCE < minimum]
    if short:
        report.add(FAIL, "viseme/min-duration",
                   f"{len(short)} event(s) under {minimum}s, first {short[0]['viseme']} "
                   f"at {short[0]['start']}s - would read as a flicker")
    else:
        report.add(PASS, "viseme/min-duration", f"all events >= {minimum}s")


def check_digest(payload, report):
    recorded = payload.get("digest")
    if not recorded:
        report.add(FAIL, "lock/digest", "no digest recorded")
        return
    recomputed = timeline_lib.digest(payload)
    if recomputed != recorded:
        report.add(FAIL, "lock/digest",
                   f"recorded {recorded[:16]}, recomputed {recomputed[:16]} - "
                   "the file was edited after it was generated")
    else:
        report.add(PASS, "lock/digest", recorded[:16])


def check_audio(payload, report):
    audio = payload.get("audio")
    if not audio:
        report.add(SKIP, "audio/present", "no audio - timings are estimates")
        return
    path = Path(audio["path"])
    if not path.is_absolute():
        path = REPO / path
    if not path.exists():
        report.add(WARN, "audio/present", f"{audio['path']} is gone - cannot re-verify")
        return
    info = audioinfo.wav_info(path)
    if info["sha256"] != audio.get("sha256"):
        report.add(FAIL, "audio/sha256",
                   "the audio file changed since this timeline was built")
    else:
        report.add(PASS, "audio/sha256", audio["sha256"][:16])
    if abs(info["duration"] - payload.get("duration", 0)) > 0.05:
        report.add(FAIL, "audio/duration",
                   f"audio is {info['duration']}s, timeline says {payload['duration']}s")
    else:
        report.add(PASS, "audio/duration", f"{info['duration']}s")
    for problem in audioinfo.format_problems(info):
        report.add(WARN, "audio/format", problem)


def check_g2p(payload, report):
    g2p = payload.get("g2p") or {}
    coverage = g2p.get("coverage")
    if coverage is None:
        report.add(SKIP, "g2p/coverage", "not recorded")
    elif coverage < COVERAGE_FLOOR:
        report.add(FAIL, "g2p/coverage",
                   f"{coverage:.1%} of Thai characters parsed, floor is "
                   f"{COVERAGE_FLOOR:.0%}")
    elif coverage < 1.0:
        report.add(WARN, "g2p/coverage",
                   f"{coverage:.1%} - some characters did not parse")
    else:
        report.add(PASS, "g2p/coverage", "100%")

    if not (payload.get("viseme_map") or {}).get("reviewed_by_thai_speaker", False):
        report.add(WARN, "mapping/review",
                   "the Thai viseme mapping has not been reviewed by a Thai speaker "
                   "(PHASE 4.2)")
    else:
        report.add(PASS, "mapping/review", "reviewed")


def validate(path, strict=False):
    report = Report()
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        report.add(FAIL, "file/readable", str(error))
        return payload_result(report, strict)

    check_structure(payload, report)
    check_events(payload, report)
    check_visemes(payload, report)
    check_flicker(payload, report)
    check_digest(payload, report)
    check_audio(payload, report)
    check_g2p(payload, report)
    return payload_result(report, strict)


def payload_result(report, strict):
    failed = report.failed() or (strict and any(
        level == WARN for level, _, _ in report.rows))
    return report, failed


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate a viseme timeline (PHASE 7.4).")
    parser.add_argument("timeline", nargs="?", help="timeline JSON to validate")
    parser.add_argument("--all", action="store_true",
                        help=f"validate every timeline in {TIMELINE_DIR}")
    parser.add_argument("--strict", action="store_true",
                        help="treat warnings as failures")
    args = parser.parse_args(argv)

    if args.all:
        targets = sorted(TIMELINE_DIR.glob("*.json"))
        if not targets:
            print(f"no timelines in {TIMELINE_DIR}")
            return 0
    elif args.timeline:
        targets = [Path(args.timeline)]
    else:
        parser.error("give a timeline path or --all")

    worst = 0
    for target in targets:
        report, failed = validate(target, args.strict)
        print(f"\n{target}")
        print(report.render())
        counts = report.counts()
        summary = "  ".join(f"{level} {count}" for level, count in sorted(counts.items()))
        print(f"  -> {'INVALID' if failed else 'valid'}   {summary}")
        worst = max(worst, 1 if failed else 0)
    return worst


if __name__ == "__main__":
    sys.exit(main())
