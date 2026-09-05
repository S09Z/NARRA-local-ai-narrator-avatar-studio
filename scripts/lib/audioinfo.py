"""WAV inspection for the audio pipeline (PHASE 7.1).

Standard library only, like every other check in this repository. `wave` reads the
header, which is all the timeline needs: how long the audio actually is, and a hash to
tie a timeline to the exact file it was built against.

Not a package (DECISIONS.md ADR-007, ADR-011).
"""

import hashlib
import wave
from pathlib import Path

# PLAN 7.1 asks for a stable sample rate. This is the one the pipeline records and
# expects; a file that disagrees is reported, not silently accepted.
EXPECTED_SAMPLE_RATE = 22050
EXPECTED_CHANNELS = 1
EXPECTED_SAMPLE_WIDTH = 2       # 16-bit signed little-endian


class AudioError(Exception):
    """The file is missing, is not a WAV, or has no readable header."""


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wav_info(path):
    """Duration, format, and hash of a WAV file."""
    path = Path(path)
    if not path.exists():
        raise AudioError(f"audio not found: {path}")
    try:
        with wave.open(str(path)) as handle:
            frames = handle.getnframes()
            rate = handle.getframerate()
            channels = handle.getnchannels()
            width = handle.getsampwidth()
    except wave.Error as error:
        raise AudioError(f"{path} is not a readable WAV: {error}") from error
    if not rate:
        raise AudioError(f"{path} reports a zero sample rate")
    return {
        "path": str(path),
        "sha256": sha256(path),
        "duration": round(frames / rate, 4),
        "sample_rate": rate,
        "channels": channels,
        "sample_width": width,
        "frames": frames,
    }


def format_problems(info):
    """Ways the file departs from what PLAN 7.1 asks for. Empty list means it conforms."""
    problems = []
    if info["sample_rate"] != EXPECTED_SAMPLE_RATE:
        problems.append(f"sample rate {info['sample_rate']} != {EXPECTED_SAMPLE_RATE}")
    if info["channels"] != EXPECTED_CHANNELS:
        problems.append(f"{info['channels']} channels, expected {EXPECTED_CHANNELS}")
    if info["sample_width"] != EXPECTED_SAMPLE_WIDTH:
        problems.append(
            f"{info['sample_width'] * 8}-bit, expected {EXPECTED_SAMPLE_WIDTH * 8}-bit")
    return problems


def write_silence(path, seconds, rate=EXPECTED_SAMPLE_RATE):
    """A silent WAV of a known length - lets the pipeline run where no TTS exists."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(round(seconds * rate))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(EXPECTED_CHANNELS)
        handle.setsampwidth(EXPECTED_SAMPLE_WIDTH)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * frames)
    return path
