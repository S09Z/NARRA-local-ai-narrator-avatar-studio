#!/usr/bin/env python3
"""Thai text to a viseme timeline (PHASE 7, end to end).

    Thai text -> G2P (7.2) -> phoneme/viseme mapping (7.3) -> timeline.json (7.4)

With --tts or --audio the timeline is fitted to real measured audio (7.1); without
either it is an estimate. The timeline records which of those happened, in
`timing_source`, because a time nobody measured should never look like one that was
measured.

Usage:
    build_timeline.py "สวัสดีครับ" --out timeline.json
    build_timeline.py "สวัสดีครับ" --tts --name greeting
    build_timeline.py "สวัสดีครับ" --audio speech.wav --out timeline.json
    build_timeline.py "สวัสดีครับ" --report          inspect the parse, write nothing
    build_timeline.py --text-file script.txt --tts --name episode-001

Exit code 0 = built, 1 = failed, 2 = usage error.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import audioinfo                                      # noqa: E402
import thai_g2p                                       # noqa: E402
import timeline as timeline_lib                       # noqa: E402
import viseme_map                                     # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tts as tts_lib                                 # noqa: E402

REPO = Path(os.environ.get("NARRA_REPO", Path(__file__).resolve().parents[2]))
TIMELINE_DIR = REPO / "metadata" / "timelines"
AUDIO_DIR = REPO / "assets" / "audio"

# A parse this poor is a broken timeline, not a slightly rough one.
COVERAGE_FLOOR = 0.95


def slugify(text):
    """A stable, filesystem-safe name for a piece of Thai text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def report(result, mapping):
    """What the parser did, syllable by syllable. The place to look when a word is wrong."""
    lines = [f"text        {result.text}",
             f"syllables   {len(result.syllables)}",
             f"coverage    {result.coverage:.1%}",
             f"ipa         {result.ipa}",
             ""]
    for syllable in result.syllables:
        shapes = []
        for phone in syllable.phones():
            visemes = viseme_map.viseme_for(phone.symbol, phone.role, mapping)
            shapes.append("/".join(visemes) if visemes else "-")
        lines.append(f"  {syllable.text:<10} /{syllable.ipa:<8}/  {' '.join(shapes)}")

    if result.unparsed:
        lines.append("")
        lines.append("  unparsed characters (add the word to docs/audio/thai-lexicon.json):")
        for position, character in result.unparsed:
            lines.append(f"    position {position}: {character!r}")

    unknown = viseme_map.unmapped_phonemes(
        [phone.symbol for phone in result.phones], mapping)
    if unknown:
        lines.append("")
        lines.append(f"  phonemes with no viseme entry: {', '.join(unknown)}")
    return "\n".join(lines)


def build(text, out=None, name=None, use_tts=False, audio=None, g2p_engine=None,
          tts_engine="say", voice=tts_lib.DEFAULT_VOICE, rate=None, character="narra"):
    """Run the pipeline and return (payload, out_path)."""
    result = thai_g2p.phonemize(text, g2p_engine)
    mapping = viseme_map.load()

    audio_info, tts_info = None, None
    if use_tts:
        target = AUDIO_DIR / f"{name or slugify(text)}.wav"
        produced = tts_lib.synthesize(text, target, tts_engine, voice, rate)
        audio_info, tts_info = produced["audio"], produced["tts"]
    elif audio:
        audio_info = audioinfo.wav_info(audio)

    payload = timeline_lib.build(
        result,
        audio_duration=audio_info["duration"] if audio_info else None,
        mapping=mapping,
        character=character,
        engine=g2p_engine or "builtin",
        audio=audio_info,
        tts=tts_info,
    )

    if out:
        out_path = Path(out)
    else:
        out_path = TIMELINE_DIR / f"{name or slugify(text)}-timeline-v1.json"
    return payload, out_path


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build a Thai viseme timeline (PHASE 7).")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("text", nargs="?", help="Thai text")
    source.add_argument("--text-file", help="read the Thai text from a file")

    parser.add_argument("--out", help="timeline JSON path")
    parser.add_argument("--name", help="basename for generated audio and timeline")
    parser.add_argument("--tts", action="store_true", help="synthesize audio first")
    parser.add_argument("--audio", help="fit to an existing WAV instead")
    parser.add_argument("--tts-engine", default="say", choices=sorted(tts_lib.ENGINES))
    parser.add_argument("--voice", default=tts_lib.DEFAULT_VOICE)
    parser.add_argument("--rate", type=int)
    parser.add_argument("--g2p-engine", help="G2P backend; default is the built-in")
    parser.add_argument("--character", default="narra")
    parser.add_argument("--report", action="store_true",
                        help="print the parse and exit without writing")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    text = (Path(args.text_file).read_text(encoding="utf-8").strip()
            if args.text_file else args.text)
    if not text.strip():
        print("error: no text", file=sys.stderr)
        return 2
    if args.tts and args.audio:
        parser.error("--tts and --audio are mutually exclusive")

    try:
        if args.report:
            result = thai_g2p.phonemize(text, args.g2p_engine)
            print(report(result, viseme_map.load()))
            return 0 if result.coverage >= COVERAGE_FLOOR else 1

        payload, out_path = build(
            text, args.out, args.name, args.tts, args.audio, args.g2p_engine,
            args.tts_engine, args.voice, args.rate, args.character)
    except (thai_g2p.LexiconError, viseme_map.VisemeMapError,
            timeline_lib.TimelineError, tts_lib.TTSError,
            audioinfo.AudioError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    timeline_lib.write(payload, out_path)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"{out_path}")
        print(f"  duration      {payload['duration']}s ({payload['timing_source']})")
        print(f"  syllables     {payload['g2p']['syllables']}")
        print(f"  events        {len(payload['events'])}")
        print(f"  visemes used  {', '.join(payload['visemes_used'])}")
        print(f"  digest        {payload['digest'][:16]}")
        if payload["g2p"]["coverage"] < 1.0:
            print(f"  warning: G2P coverage {payload['g2p']['coverage']:.1%} - "
                  "run --report to see what did not parse")
        if not payload["viseme_map"]["reviewed_by_thai_speaker"]:
            print("  warning: the Thai viseme mapping has not been reviewed by a "
                  "Thai speaker (PHASE 4.2)")

    if payload["g2p"]["coverage"] < COVERAGE_FLOOR:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
