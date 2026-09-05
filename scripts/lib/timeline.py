"""Viseme timeline - phones plus timing to the JSON PHASE 8 consumes (PHASE 7.4).

The shape is the one PLAN 7.4 specifies - a duration and a list of events carrying
start, end, phoneme, and viseme - with the provenance fields this repository requires of
anything reproducible (CLAUDE.md, Reproducibility).

The honest part is `timing_source`, which says how much the times are worth:

    estimated  no audio existed. Durations come from the class model in
               docs/audio/thai-duration-model.json and the total is a guess.
    fitted     audio existed and its duration was measured. The estimates set the
               proportions and are scaled so the total matches the real audio.
    aligned    a forced aligner produced the times. Nothing here does this yet; the
               field exists so PHASE 8 can tell the difference without guessing.

Two rules from docs/thai-viseme/thai-viseme-mapping.md are enforced here rather than
left to the animator: /h/ and /ʔ/ have no visible articulation and give their time to
the neighbouring vowel (section 1), and a viseme too short to read is absorbed rather
than emitted as a flicker (section 6).

Coarticulation is deliberately absent. Section 6 assigns blend weights, hold-versus-
transition, and stress to PHASE 8. This module emits target shapes and honest times.

Not a package (DECISIONS.md ADR-007, ADR-011).
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import viseme_map

DEFAULT_MODEL = (Path(__file__).resolve().parents[2]
                 / "docs" / "audio" / "thai-duration-model.json")

SCHEMA_VERSION = "1.0"
ESTIMATED, FITTED, ALIGNED = "estimated", "fitted", "aligned"

_MODEL_CACHE = {}


class TimelineError(Exception):
    """The timeline cannot be built from what was given."""


def load_model(path=None):
    key = str(path) if path else "default"
    if key not in _MODEL_CACHE:
        target = Path(path) if path else DEFAULT_MODEL
        if not target.exists():
            raise TimelineError(f"duration model not found: {target}")
        _MODEL_CACHE[key] = json.loads(target.read_text(encoding="utf-8"))
    return _MODEL_CACHE[key]


def phoneme_class(phoneme, role, model):
    """Duration class for one phoneme in one role, or None if the model has no view."""
    if role == "final":
        found = model["final_class"].get(phoneme)
        if found:
            return found
    return model["phoneme_class"].get(phoneme)


def _unit_duration(phoneme, role, model):
    name = phoneme_class(phoneme, role, model)
    if name is None:
        name = "vowel_short" if role == "vowel" else "stop"
    return model["class_duration_s"][name]


def _units(result, mapping, model):
    """Phones to (visemes, seconds, phoneme, role, syllable), silent phones included."""
    units = []
    for phone in result.phones:
        visemes = viseme_map.viseme_for(phone.symbol, phone.role, mapping)
        seconds = _unit_duration(phone.symbol, phone.role, model)
        units.append([visemes, seconds, phone.symbol, phone.role, phone.syllable])
    return units


def _absorb_silent(units):
    """/h/ and /ʔ/ hold the following vowel - mapping.md section 1.

    Their time is real time in the audio, so it is handed to a neighbour rather than
    deleted. Forward first, because the rule is about the vowel that follows.
    """
    kept = []
    pending = 0.0
    for visemes, seconds, phoneme, role, syllable in units:
        if not visemes:
            pending += seconds
            continue
        kept.append([visemes, seconds + pending, phoneme, role, syllable])
        pending = 0.0
    if pending:
        if kept:
            kept[-1][1] += pending
        # else: the whole utterance was silent phones; the REST padding covers it.
    return kept


def _expand(units):
    """One event per viseme. A diphthong is two shapes sharing the vowel's time."""
    events = []
    for visemes, seconds, phoneme, role, syllable in units:
        share = seconds / len(visemes)
        for viseme in visemes:
            events.append({"viseme": viseme, "seconds": share, "phoneme": phoneme,
                           "role": role, "syllable": syllable})
    return events


def _merge_identical(events):
    """Adjacent identical shapes are one hold, not two - /n/ + /n/ never re-articulates."""
    merged = []
    for event in events:
        if merged and merged[-1]["viseme"] == event["viseme"]:
            merged[-1]["seconds"] += event["seconds"]
            merged[-1]["phoneme"] = f"{merged[-1]['phoneme']}+{event['phoneme']}"
            continue
        merged.append(dict(event))
    return merged


def _absorb_short(events, minimum):
    """Absorb anything too short to read - mapping.md section 6, flicker.

    Absorbed into the longer neighbour, so the total duration is untouched: these
    times describe real audio and must keep summing to it.
    """
    absorbed = []
    working = [dict(event) for event in events]
    while len(working) > 1:
        index = min(range(len(working)), key=lambda i: working[i]["seconds"])
        if working[index]["seconds"] >= minimum:
            break
        short = working.pop(index)
        before = working[index - 1] if index > 0 else None
        after = working[index] if index < len(working) else None
        if before and (not after or before["seconds"] >= after["seconds"]):
            before["seconds"] += short["seconds"]
        else:
            after["seconds"] += short["seconds"]
        absorbed.append({"viseme": short["viseme"], "phoneme": short["phoneme"],
                         "seconds": round(short["seconds"], 4)})
    return working, absorbed


def _settle(sequence, minimum, max_passes=16):
    """Absorb and merge until neither changes anything.

    One pass is not enough: absorbing a too-short /w/ from between two /a/ leaves two
    identical neighbouring shapes, which then have to become one hold. Each pass can
    only shorten the list, so this terminates.
    """
    absorbed = []
    for _ in range(max_passes):
        before = len(sequence)
        sequence, just_absorbed = _absorb_short(sequence, minimum)
        absorbed.extend(just_absorbed)
        sequence = _merge_identical(sequence)
        if len(sequence) == before:
            break
    return sequence, absorbed


def _pad(events, model, mapping, breaks, syllable_count):
    """REST at the start, at phrase breaks, and at the end - mapping.md section 5."""
    rest = viseme_map.silence(mapping)
    gap = model.get("word_gap_s", 0.0)
    tail = model.get("sentence_final_rest_s", 0.15)

    padded = [{"viseme": rest, "seconds": tail, "phoneme": None, "role": "silence",
               "syllable": None}]
    break_set = set(breaks or [])
    for event in events:
        padded.append(event)
        if gap and event["syllable"] in break_set and event["syllable"] is not None:
            padded.append({"viseme": rest, "seconds": gap, "phoneme": None,
                           "role": "silence", "syllable": event["syllable"]})
    padded.append({"viseme": rest, "seconds": tail, "phoneme": None, "role": "silence",
                   "syllable": syllable_count - 1 if syllable_count else None})
    return padded


def _to_events(sequence, precision=3):
    """Cumulative times. Rounded once, at the end, so starts and ends stay flush."""
    events = []
    cursor = 0.0
    for entry in sequence:
        start = cursor
        cursor += entry["seconds"]
        events.append({
            "start": round(start, precision),
            "end": round(cursor, precision),
            "phoneme": entry["phoneme"],
            "viseme": entry["viseme"],
            "role": entry["role"],
            "syllable": entry["syllable"],
        })
    return events


def digest(payload):
    """Stable hash of everything that decides the animation, timestamp excluded.

    Two runs of the same text through the same settings must be recognisably the same
    timeline, the way two runs of the same seed must be the same image.
    """
    material = {
        "text": payload.get("text"),
        "events": payload.get("events"),
        "timing_source": payload.get("timing_source"),
        "g2p": payload.get("g2p", {}).get("engine"),
        "viseme_map": payload.get("viseme_map"),
        "duration_model": payload.get("duration_model"),
    }
    blob = json.dumps(material, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def build(result, audio_duration=None, mapping=None, model=None, character="narra",
          engine="builtin", audio=None, tts=None, generated=None):
    """Build a timeline from a G2P result, fitted to audio duration when one is known."""
    mapping = mapping or viseme_map.load()
    model = model or load_model()

    units = _absorb_silent(_units(result, mapping, model))
    sequence = _merge_identical(_expand(units))
    sequence = _pad(sequence, model, mapping, result.breaks, len(result.syllables))

    estimated_total = sum(entry["seconds"] for entry in sequence)
    if audio_duration and estimated_total > 0:
        scale = audio_duration / estimated_total
        for entry in sequence:
            entry["seconds"] *= scale
        timing_source = FITTED
        total = audio_duration
    else:
        scale = 1.0
        timing_source = ESTIMATED
        total = estimated_total

    minimum = model.get("min_viseme_duration_s", 0.0)
    sequence, absorbed = _settle(sequence, minimum)
    events = _to_events(sequence)

    map_data = mapping
    payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": "7.4",
        "character": character,
        "language": "th",
        "text": result.text,
        "duration": round(total, 3),
        "timing_source": timing_source,
        "idle_viseme": viseme_map.silence(mapping),
        "g2p": {
            "engine": engine,
            "ipa": result.ipa,
            "syllables": len(result.syllables),
            "coverage": round(result.coverage, 4),
            "unparsed": [{"position": position, "character": character_}
                         for position, character_ in result.unparsed],
        },
        "viseme_map": {
            "version": map_data.get("version"),
            "source": map_data.get("source"),
            "reviewed_by_thai_speaker": map_data.get("reviewed_by_thai_speaker", False),
        },
        "duration_model": {
            "version": model.get("version"),
            "scale": round(scale, 6),
            "min_viseme_duration_s": minimum,
        },
        "audio": audio,
        "tts": tts,
        "absorbed_events": absorbed,
        "visemes_used": sorted({event["viseme"] for event in events}),
        "events": events,
    }
    payload["generated"] = generated or datetime.now(timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")
    payload["digest"] = digest(payload)
    return payload


def write(payload, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path
