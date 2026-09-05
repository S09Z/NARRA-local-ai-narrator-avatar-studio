#!/usr/bin/env python3
"""Thai text to WAV, through a pluggable engine (PHASE 7.1).

PLAN 7.1 asks for a Thai-compatible TTS engine producing WAV at a stable sample rate,
deterministic where possible. It does not say which engine, and the answer differs by
machine: this repository targets an RTX 5070 box that does not exist yet, while the
work is being done on a Mac. So the engine is an adapter, chosen at the command line,
and the pipeline records which one produced a file (DECISIONS.md ADR-021).

Engines:

    say        macOS `say` with the Thai voice Kanya. Available with no install, and
               deterministic - the same text yields a byte-identical WAV. macOS only,
               so it is the development engine, not the production one.
    silence    A silent WAV of an estimated length. Not speech. It exists so the rest
               of the pipeline can be exercised and tested on a machine with no Thai
               TTS at all, and so CI never depends on a platform binary.

Selecting the production engine is deferred until the target machine exists; the
criteria and candidates are in docs/audio/phase-7-audio-pipeline.md.

Usage:
    tts.py "สวัสดีครับ" -o out.wav
    tts.py "สวัสดีครับ" -o out.wav --engine say --voice Kanya
    tts.py --list
    tts.py "สวัสดีครับ" --check-determinism

Exit code 0 = success, 1 = synthesis failed, 2 = usage error.
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import audioinfo                                      # noqa: E402
import thai_g2p                                       # noqa: E402
import timeline as timeline_lib                       # noqa: E402

REPO = Path(os.environ.get("NARRA_REPO", Path(__file__).resolve().parents[2]))

DEFAULT_VOICE = "Kanya"        # the only th_TH voice macOS ships
SAMPLE_RATE = audioinfo.EXPECTED_SAMPLE_RATE


class TTSError(Exception):
    """Synthesis failed, or the requested engine is not usable on this machine."""


def say_available():
    return platform.system() == "Darwin" and shutil.which("say") is not None


def say_voices(language="th_TH"):
    """Thai voices macOS reports, or an empty list if `say` is not usable."""
    if not say_available():
        return []
    result = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
    voices = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1 if len(parts) == 2 else 1] and language in line:
            voices.append(parts[0])
    return voices


def _macos_version():
    result = subprocess.run(["sw_vers", "-productVersion"], capture_output=True,
                            text=True)
    return result.stdout.strip() or "unknown"


def synthesize_say(text, out_path, voice=DEFAULT_VOICE, rate=None):
    """macOS `say`. LEI16 at 22050 Hz mono, which is what audioinfo expects."""
    if not say_available():
        raise TTSError("the `say` engine needs macOS; use --engine silence elsewhere")
    if voice not in say_voices():
        available = ", ".join(say_voices()) or "none"
        raise TTSError(f"no Thai voice {voice!r} on this machine - have: {available}")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    command = ["say", "-v", voice, "-o", str(out_path),
               f"--data-format=LEI16@{SAMPLE_RATE}"]
    if rate:
        command += ["-r", str(rate)]
    command.append(text)

    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0 or not out_path.exists():
        raise TTSError(f"say failed: {result.stderr.strip() or result.returncode}")
    return {"engine": "say", "voice": voice, "rate": rate,
            "engine_version": f"macOS {_macos_version()}",
            "deterministic": True}


def synthesize_silence(text, out_path, voice=None, rate=None):
    """A silent WAV as long as the duration model thinks the text takes to say."""
    result = thai_g2p.phonemize(text)
    estimate = timeline_lib.build(result, generated="1970-01-01T00:00:00Z")["duration"]
    audioinfo.write_silence(out_path, estimate, SAMPLE_RATE)
    return {"engine": "silence", "voice": None, "rate": None,
            "engine_version": "builtin",
            "deterministic": True,
            "note": "silent placeholder, not speech - timings are estimates"}


ENGINES = {"say": synthesize_say, "silence": synthesize_silence}


def synthesize(text, out_path, engine="say", voice=DEFAULT_VOICE, rate=None):
    """Synthesize and return the merged TTS and audio metadata."""
    if engine not in ENGINES:
        raise TTSError(f"unknown engine {engine!r} - have {', '.join(sorted(ENGINES))}")
    if not text.strip():
        raise TTSError("nothing to synthesize")
    meta = ENGINES[engine](text, out_path, voice, rate)
    info = audioinfo.wav_info(out_path)
    problems = audioinfo.format_problems(info)
    if problems:
        meta["format_problems"] = problems
    return {"tts": meta, "audio": info}


def check_determinism(text, engine, voice, rate):
    """Synthesize twice and compare. PLAN 7.1 asks for deterministic where possible."""
    with tempfile.TemporaryDirectory() as work:
        first = synthesize(text, Path(work) / "a.wav", engine, voice, rate)
        second = synthesize(text, Path(work) / "b.wav", engine, voice, rate)
    return first["audio"]["sha256"] == second["audio"]["sha256"], first, second


def available_engines():
    return {"say": say_available(), "silence": True}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Synthesize Thai speech to WAV (PHASE 7.1).")
    parser.add_argument("text", nargs="?", help="Thai text to speak")
    parser.add_argument("-o", "--out", help="output WAV path")
    parser.add_argument("--engine", default="say", choices=sorted(ENGINES))
    parser.add_argument("--voice", default=DEFAULT_VOICE)
    parser.add_argument("--rate", type=int, help="words per minute, engine permitting")
    parser.add_argument("--list", action="store_true",
                        help="show engines and Thai voices on this machine")
    parser.add_argument("--check-determinism", action="store_true",
                        help="synthesize twice and compare hashes")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    if args.list:
        report = {"engines": available_engines(), "thai_voices": say_voices(),
                  "platform": platform.system()}
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print("Engines:")
            for name, usable in report["engines"].items():
                print(f"  [{'available' if usable else 'unavailable'}] {name}")
            print(f"Thai voices: {', '.join(report['thai_voices']) or 'none'}")
        return 0

    if not args.text:
        parser.error("text is required unless --list is given")

    try:
        if args.check_determinism:
            same, first, _ = check_determinism(args.text, args.engine, args.voice,
                                               args.rate)
            print(f"{args.engine}: {'deterministic' if same else 'NOT deterministic'} "
                  f"({first['audio']['sha256'][:16]})")
            return 0 if same else 1

        if not args.out:
            parser.error("-o/--out is required when synthesizing")
        result = synthesize(args.text, args.out, args.engine, args.voice, args.rate)
    except TTSError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except audioinfo.AudioError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        audio = result["audio"]
        print(f"{args.out}  {audio['duration']}s  {audio['sample_rate']}Hz  "
              f"{audio['channels']}ch  {audio['sha256'][:16]}")
        for problem in result["tts"].get("format_problems", []):
            print(f"  warning: {problem}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
