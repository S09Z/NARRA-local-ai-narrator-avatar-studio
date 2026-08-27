#!/usr/bin/env python3
"""Viseme timeline to a frame plan (PHASE 8).

    timeline.json (PHASE 7) + narrator state -> animation.json

The plan says, for every frame, which visemes are on screen at what weight, which
expression is underneath, and what the idle motion is doing. It renders nothing: PHASE 9
is the renderer, and keeping the plan separate means it can be inspected, diffed, and
validated before a single pixel is touched.

Usage:
    build_animation.py timeline.json --out animation.json
    build_animation.py timeline.json --state explaining --fps 30
    build_animation.py --text "สวัสดีครับ" --tts --name greeting
    build_animation.py timeline.json --expression-plan plan.json

An expression plan is a list of segments, and is how PLAN 8.3's independence is used:

    [{"start": 0.0, "end": 1.2, "expression": "neutral"},
     {"start": 1.2, "end": 3.0, "expression": "happy"}]

Exit code 0 = built, 1 = failed, 2 = usage error.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import animation as animation_lib                     # noqa: E402
import canon                                          # noqa: E402
import thai_g2p                                       # noqa: E402
import timeline as timeline_lib                       # noqa: E402
import viseme_map                                     # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "audio"))
import tts as tts_lib                                 # noqa: E402

REPO = Path(os.environ.get("NARRA_REPO", Path(__file__).resolve().parents[2]))
STATES = REPO / "character" / "compositions" / "narrator-states.json"
ANIMATION_DIR = REPO / "metadata" / "animations"
AUDIO_DIR = REPO / "assets" / "audio"


def load_states():
    if not STATES.exists():
        raise animation_lib.AnimationError(f"narrator states not found: {STATES}")
    return json.loads(STATES.read_text(encoding="utf-8"))["states"]


def timeline_from_text(text, use_tts, name, tts_engine, voice):
    """Convenience path - run PHASE 7 inline so one command goes text to frame plan."""
    result = thai_g2p.phonemize(text)
    audio, tts_meta = None, None
    if use_tts:
        produced = tts_lib.synthesize(text, AUDIO_DIR / f"{name or 'animation'}.wav",
                                      tts_engine, voice, None)
        audio, tts_meta = produced["audio"], produced["tts"]
    return timeline_lib.build(result, audio_duration=audio["duration"] if audio else None,
                              mapping=viseme_map.load(), audio=audio, tts=tts_meta)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build a lip-sync frame plan (PHASE 8).")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("timeline", nargs="?", help="PHASE 7 timeline JSON")
    source.add_argument("--text", help="Thai text - runs PHASE 7 inline")

    parser.add_argument("--state", default="talking", help="narrator state")
    parser.add_argument("--fps", type=int, help="frames per second")
    parser.add_argument("--expression-plan", help="JSON list of expression segments")
    parser.add_argument("--out", help="animation JSON path")
    parser.add_argument("--name", help="basename for generated files")
    parser.add_argument("--tts", action="store_true", help="synthesize audio (with --text)")
    parser.add_argument("--tts-engine", default="say", choices=sorted(tts_lib.ENGINES))
    parser.add_argument("--voice", default=tts_lib.DEFAULT_VOICE)
    parser.add_argument("--character", default="narra")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        states = load_states()
        if args.state not in states:
            print(f"error: unknown state {args.state!r} - have "
                  f"{', '.join(sorted(states))}", file=sys.stderr)
            return 1
        state = states[args.state]

        if args.text:
            payload_timeline = timeline_from_text(args.text, args.tts, args.name,
                                                  args.tts_engine, args.voice)
        else:
            payload_timeline = json.loads(
                Path(args.timeline).read_text(encoding="utf-8"))

        plan = None
        if args.expression_plan:
            plan = json.loads(Path(args.expression_plan).read_text(encoding="utf-8"))

        payload = animation_lib.build(
            payload_timeline, state, args.state, args.fps, plan,
            character=args.character,
            generated=datetime.now(timezone.utc).isoformat(
                timespec="seconds").replace("+00:00", "Z"))
    except (animation_lib.AnimationError, timeline_lib.TimelineError,
            viseme_map.VisemeMapError, tts_lib.TTSError, thai_g2p.LexiconError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except (OSError, json.JSONDecodeError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    name = args.name or (payload["source_timeline"]["digest"] or "animation")[:12]
    out_path = Path(args.out) if args.out else ANIMATION_DIR / f"{name}-animation-v1.json"
    animation_lib.write(payload, out_path)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        meta = payload["mouth_meta"]
        print(f"{out_path}")
        print(f"  state         {payload['state']} "
              f"({payload['mouth_mode']}, {payload['pose']}/{payload['camera_class']})")
        print(f"  fps           {payload['fps']}")
        print(f"  frames        {payload['frame_count']} over {payload['duration']}s")
        print(f"  expressions   "
              f"{', '.join(s['expression'] for s in payload['tracks']['expression'])}")
        print(f"  blinks        {len(payload['tracks']['blink'])}")
        print(f"  digest        {payload['digest'][:16]}")
        if meta["absorbed"]:
            visemes = ", ".join(entry["viseme"] for entry in meta["absorbed"])
            print(f"  note: {len(meta['absorbed'])} viseme(s) absorbed as too brief to "
                  f"read at {payload['fps']}fps: {visemes}")
        for entry in meta["extended"]:
            if entry.get("given"):
                print(f"  note: closure {entry['viseme']} extended by "
                      f"{entry['given']}s to stay visible")
            else:
                print(f"  warning: closure {entry['viseme']} could not be extended - "
                      f"{entry.get('reason')}")
        for entry in meta["closures"]:
            if not entry.get("resolved"):
                print(f"  warning: closure {entry['viseme']} unresolved - "
                      f"{entry.get('reason')}")
        if payload["source_timeline"]["timing_source"] == "estimated":
            print("  warning: the source timeline is estimated - no audio was measured")
    return 0


if __name__ == "__main__":
    sys.exit(main())
