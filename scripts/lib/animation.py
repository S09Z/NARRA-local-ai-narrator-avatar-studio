"""Lip-sync animation engine - a viseme timeline becomes a frame plan (PHASE 8).

Input is a PHASE 7 timeline (PLAN 7.4) and a narrator state. Output is a frame-accurate
plan: for every frame, which visemes are on screen and at what weight, which expression
is underneath, and what the idle motion is doing.

The four parts are PLAN 8.1 to 8.4:

    8.1 mouth switching    REST -> viseme -> REST, quantised to frames
    8.2 coarticulation     weights blended across previous/current/next
    8.3 expression layer   independent of the mouth (ADR-004, ADR-012)
    8.4 secondary          blink, breath, head sway, brow - procedural and seeded

Three rules here are not stylistic choices, they come from
docs/thai-viseme/thai-viseme-mapping.md and getting them wrong makes Thai lip-sync look
foreign:

    A final stop is unreleased (section 3). The closure holds for its whole event and
    the transition out of it happens after the boundary, not across it.

    MBP must actually close (section 5, CLAUDE.md). A bilabial blended so hard it never
    reaches full weight reads as a different consonant, so closures are protected from
    absorption and pinned to full weight on at least one frame.

    A rounded vowel starts early (section 6). /k/ before /u/ is already rounding, so U,
    O and AO reach backwards further than a normal blend.

Not a package (DECISIONS.md ADR-007, ADR-011).
"""

import hashlib
import json
import math
import random
from pathlib import Path

import canon

DOCS = Path(__file__).resolve().parents[2] / "docs" / "animation"
DEFAULT_COARTICULATION = DOCS / "coarticulation-model.json"
DEFAULT_SECONDARY = DOCS / "secondary-animation.json"

SCHEMA_VERSION = "1.0"

_CACHE = {}


class AnimationError(Exception):
    """The animation cannot be built from what was given."""


def _load_json(path):
    key = str(path)
    if key not in _CACHE:
        target = Path(path)
        if not target.exists():
            raise AnimationError(f"model not found: {target}")
        _CACHE[key] = json.loads(target.read_text(encoding="utf-8"))
    return _CACHE[key]


def load_coarticulation(path=None):
    return _load_json(path or DEFAULT_COARTICULATION)


def load_secondary(path=None):
    return _load_json(path or DEFAULT_SECONDARY)


# --- 8.1 mouth switching --------------------------------------------------------------

def _frames_for(seconds, fps):
    return seconds * fps


def absorb_short_events(events, fps, model):
    """Enforce the flicker rule in frames, protecting closures.

    PHASE 7 enforced a minimum in seconds without knowing the frame rate. Frames are
    what reach the eye, so the rule is restated here - and it acquires an exception.
    Absorbing a short MBP would delete a bilabial closure, which does not make the
    animation smoother, it makes it a different word. Closures are extended instead.
    """
    minimum = model["min_frames_on_screen"] / fps
    closures = set(model["closure_visemes"])
    working = [dict(event) for event in events]
    absorbed, extended = [], []

    working = _merge_adjacent(working)
    guard = 0
    while len(working) > 1 and guard < 1000:
        guard += 1
        index = min(range(len(working)),
                    key=lambda i: working[i]["end"] - working[i]["start"])
        span = working[index]["end"] - working[index]["start"]
        if span >= minimum - 1e-9:
            break

        event = working[index]
        before = working[index - 1] if index > 0 else None
        after = working[index + 1] if index + 1 < len(working) else None

        if event["viseme"] in closures:
            needed = minimum - span
            donors = [entry for entry in (before, after) if entry is not None]
            donors.sort(key=lambda entry: entry["end"] - entry["start"], reverse=True)
            if not donors or (donors[0]["end"] - donors[0]["start"]) - needed < minimum:
                extended.append({"viseme": event["viseme"], "wanted": round(needed, 4),
                                 "given": 0.0,
                                 "reason": "no neighbour long enough to donate"})
                break
            donor = donors[0]
            if donor is before:
                before["end"] -= needed
                event["start"] -= needed
            else:
                after["start"] += needed
                event["end"] += needed
            extended.append({"viseme": event["viseme"], "wanted": round(needed, 4),
                             "given": round(needed, 4)})
            continue

        working.pop(index)
        if before and (not after or (before["end"] - before["start"])
                       >= (after["end"] - after["start"])):
            before["end"] = event["end"]
        elif after:
            after["start"] = event["start"]
        absorbed.append({"viseme": event["viseme"], "seconds": round(span, 4),
                         "phoneme": event.get("phoneme")})
        working = _merge_adjacent(working)
    return working, absorbed, extended


def _merge_adjacent(events):
    """Two neighbouring events with the same shape are one hold.

    PHASE 7 already merges these, but absorbing a short event from between two
    identical neighbours recreates the situation, and a shape cannot crossfade with
    itself - it would appear twice in the same frame at partial weight.
    """
    merged = []
    for event in events:
        if merged and merged[-1]["viseme"] == event["viseme"]:
            merged[-1]["end"] = event["end"]
            continue
        merged.append(dict(event))
    return merged


# --- 8.2 coarticulation ---------------------------------------------------------------

def _smoothstep(x):
    """Ease in and out. A linear crossfade reads mechanical on a mouth."""
    x = min(1.0, max(0.0, x))
    return x * x * (3.0 - 2.0 * x)


def boundary_windows(events, model):
    """Transition extents (before, after) for each boundary between events.

    Normally the crossfade straddles the boundary evenly. Two rules bend it:
    an unreleased final holds to its end so the whole transition is pushed after the
    boundary, and a rounded vowel starts early so most of the transition happens before.
    """
    blend = model["blend_ms"] / 1000.0
    anticipatory = model["anticipatory_blend_ms"] / 1000.0
    unreleased = set(model["unreleased_finals"])
    rounded = set(model["rounded_visemes"])

    windows = []
    for current, following in zip(events, events[1:]):
        width = blend
        before_share, after_share = 0.5, 0.5

        if following["viseme"] in rounded:
            width = anticipatory
            before_share, after_share = 0.7, 0.3      # the lips round ahead of time

        # The outgoing articulation is what matters, and PHASE 7 may have merged a
        # final into the initial that follows it ("t̚+d"). The closure rule applies to
        # a final stop that is still closed at the boundary - if an initial opened into
        # a vowel after it, that release is real and must not be suppressed.
        outgoing = (current.get("phoneme") or "").split("+")[-1]
        if outgoing in unreleased:
            before_share, after_share = 0.0, 1.0      # the closure does not pop open

        current_span = current["end"] - current["start"]
        following_span = following["end"] - following["start"]
        width = min(width, 0.9 * current_span, 0.9 * following_span)
        windows.append((width * before_share, width * after_share))
    return windows


def _weight_at(events, windows, index, time):
    """Influence of one event at one instant, before normalisation."""
    event = events[index]
    rise_start, rise_end = event["start"], event["start"]
    if index > 0:
        before, after = windows[index - 1]
        rise_start, rise_end = event["start"] - before, event["start"] + after

    fall_start, fall_end = event["end"], event["end"]
    if index < len(events) - 1:
        before, after = windows[index]
        fall_start, fall_end = event["end"] - before, event["end"] + after

    if time <= rise_start or time >= fall_end:
        return 0.0
    if time < rise_end and rise_end > rise_start:
        return _smoothstep((time - rise_start) / (rise_end - rise_start))
    if time > fall_start and fall_end > fall_start:
        return 1.0 - _smoothstep((time - fall_start) / (fall_end - fall_start))
    return 1.0


def frame_layers(events, windows, time, model):
    """Normalised viseme weights at one instant, capped at max_simultaneous_layers."""
    raw = []
    for index in range(len(events)):
        weight = _weight_at(events, windows, index, time)
        if weight > 1e-6:
            raw.append((events[index]["viseme"], weight, index))
    if not raw:
        return [{"viseme": model["idle_viseme"], "weight": 1.0}]

    # Two events can carry the same shape across a boundary; they are one layer,
    # not two partial ones.
    combined = {}
    for viseme, weight, _ in raw:
        combined[viseme] = combined.get(viseme, 0.0) + weight

    ordered = sorted(combined.items(), key=lambda item: item[1], reverse=True)
    ordered = ordered[:model["max_simultaneous_layers"]]
    total = sum(weight for _, weight in ordered)
    return [{"viseme": viseme, "weight": round(weight / total, 4)}
            for viseme, weight in ordered]


def pin_closures(frames, events, model):
    """Guarantee every closure reaches full weight on at least one frame.

    A /p/ that is never fully closed is not a softer /p/, it is a different consonant.
    Where blending has eaten the closure, the frame nearest the event's centre is forced
    to it - and the fact is recorded rather than done quietly.
    """
    closures = set(model["closure_visemes"])
    pinned = []
    for event in events:
        if event["viseme"] not in closures:
            continue
        covered = [frame for frame in frames
                   if event["start"] - 1e-9 <= frame["time"] <= event["end"] + 1e-9]
        if not covered:
            pinned.append({"viseme": event["viseme"], "start": event["start"],
                           "resolved": False,
                           "reason": "the closure falls between two frames"})
            continue
        if any(layer["viseme"] == event["viseme"] and layer["weight"] >= 0.999
               for frame in covered for layer in frame["layers"]):
            continue
        centre = (event["start"] + event["end"]) / 2.0
        target = min(covered, key=lambda frame: abs(frame["time"] - centre))
        target["layers"] = [{"viseme": event["viseme"], "weight": 1.0}]
        target["closure_pinned"] = True
        pinned.append({"viseme": event["viseme"], "frame": target["frame"],
                       "resolved": True})
    return pinned


def mouth_track(events, fps, model):
    """PLAN 8.1 and 8.2 - events to per-frame blended layers."""
    events, absorbed, extended = absorb_short_events(events, fps, model)
    windows = boundary_windows(events, model)
    duration = events[-1]["end"] if events else 0.0
    count = max(1, int(round(duration * fps)))

    frames = []
    for index in range(count):
        time = index / fps
        frames.append({"frame": index, "time": round(time, 4),
                       "layers": frame_layers(events, windows, time, model)})
    pinned = pin_closures(frames, events, model)
    return frames, {"absorbed": absorbed, "extended": extended, "closures": pinned,
                    "events_after_absorption": len(events)}


# --- 8.3 expression layer -------------------------------------------------------------

def expression_segments(plan, duration, default_expression):
    """Normalise an expression plan into contiguous segments covering the duration."""
    if not plan:
        return [{"start": 0.0, "end": round(duration, 3),
                 "expression": default_expression}]

    segments = []
    for entry in sorted(plan, key=lambda item: item["start"]):
        segments.append({"start": float(entry["start"]),
                         "end": float(entry["end"]),
                         "expression": entry["expression"]})
    for segment in segments:
        if canon.index_of("expression", segment["expression"]) is None:
            raise AnimationError(
                f"{segment['expression']!r} is not in the canonical expression set")
    if abs(segments[0]["start"]) > 1e-6:
        segments.insert(0, {"start": 0.0, "end": segments[0]["start"],
                            "expression": default_expression})
    if abs(segments[-1]["end"] - duration) > 1e-6:
        segments.append({"start": segments[-1]["end"], "end": round(duration, 3),
                         "expression": default_expression})
    return segments


def check_expression_layer(segments, mouth_mode):
    """ADR-012 - an open-mouth expression cannot host a viseme track.

    The mouth is already spent, so compositing a viseme over it renders two mouths.
    validate_compositions.py enforces this for a static state; here it has to hold over
    time, because an expression plan can put an open mouth under a track mid-sentence.
    """
    if mouth_mode != "viseme-track":
        return []
    return [segment for segment in segments
            if segment["expression"] in canon.OPEN_MOUTH_EXPRESSIONS]


# --- 8.4 secondary animation ----------------------------------------------------------

def _silence_spans(events, idle):
    return [(event["start"], event["end"]) for event in events
            if event["viseme"] == idle]


def blink_track(duration, seed, events, model, idle):
    """Deterministic blinks, pulled towards pauses.

    Seeded from the source timeline's digest so the same narration always blinks the
    same way. The image pipeline locks a seed; idle motion should not be looser.
    """
    settings = model["blink"]
    rng = random.Random(seed)
    silences = _silence_spans(events, idle)
    margin = settings["edge_margin_s"]
    span = settings["duration_s"]

    blinks = []
    time = margin + rng.uniform(0.0, settings["mean_interval_s"])
    while time + span < duration - margin:
        placed = time
        if settings.get("prefer_silence"):
            for start, end in silences:
                centre = (start + end) / 2.0
                if abs(centre - time) < settings["mean_interval_s"] / 2.0:
                    placed = min(max(centre - span / 2.0, margin),
                                 duration - margin - span)
                    break
        blinks.append({"start": round(placed, 3), "end": round(placed + span, 3)})
        time += max(0.5, settings["mean_interval_s"]
                    + rng.uniform(-settings["jitter_s"], settings["jitter_s"]))
    return blinks


def _sine_track(duration, fps, period, amplitude, phase=0.0):
    count = max(1, int(round(duration * fps)))
    return [round(amplitude * math.sin(2 * math.pi * ((index / fps) / period) + phase), 5)
            for index in range(count)]


def secondary_tracks(duration, fps, seed, events, model, idle):
    """PLAN 8.4 - blink, breath, head sway, brow, as normalised keyframe tracks."""
    breath = model["breath"]
    sway = model["head_sway"]
    return {
        "blink": blink_track(duration, seed, events, model, idle),
        "breath": {"axis": breath["axis"], "amplitude": breath["amplitude"],
                   "values": _sine_track(duration, fps, breath["period_s"],
                                         breath["amplitude"])},
        "head_sway": {
            "x": _sine_track(duration, fps, sway["period_x_s"], sway["amplitude_x"]),
            "y": _sine_track(duration, fps, sway["period_y_s"], sway["amplitude_y"],
                             phase=math.pi / 3),
        },
    }


def brow_track(segments, model):
    """A brow accent where the expression changes - where a real face punctuates."""
    settings = model["brow"]
    if not settings.get("on_expression_change"):
        return []
    accents = []
    for previous, current in zip(segments, segments[1:]):
        if previous["expression"] != current["expression"]:
            accents.append({"start": round(current["start"], 3),
                            "end": round(current["start"]
                                         + settings["accent_duration_s"], 3),
                            "amplitude": settings["amplitude"],
                            "into": current["expression"]})
    return accents


# --- assembly -------------------------------------------------------------------------

def digest(payload):
    """Stable hash of the plan, timestamp excluded - the same contract as PHASE 7."""
    material = {
        "fps": payload.get("fps"),
        "state": payload.get("state"),
        "mouth": payload.get("tracks", {}).get("mouth"),
        "expression": payload.get("tracks", {}).get("expression"),
        "source_timeline": payload.get("source_timeline", {}).get("digest"),
        "coarticulation": payload.get("coarticulation"),
    }
    blob = json.dumps(material, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def build(timeline_payload, state, state_name="talking", fps=None,
          expression_plan=None, coarticulation=None, secondary=None,
          character="narra", generated=None):
    """Assemble the full frame plan."""
    coarticulation = coarticulation or load_coarticulation()
    secondary = secondary or load_secondary()
    # `or` would swallow an explicit 0 and silently substitute the default.
    fps = coarticulation["fps_default"] if fps is None else fps
    if not isinstance(fps, int) or fps <= 0:
        raise AnimationError(f"fps must be a positive integer, got {fps!r}")

    duration = timeline_payload["duration"]
    idle = coarticulation["idle_viseme"]
    mouth_mode = state.get("mouth", "viseme-track")

    segments = expression_segments(expression_plan, duration, state["expression"])
    conflicts = check_expression_layer(segments, mouth_mode)
    if conflicts:
        names = ", ".join(sorted({segment["expression"] for segment in conflicts}))
        raise AnimationError(
            f"expression {names} has an open mouth and cannot host a viseme track "
            f"(DECISIONS.md ADR-012) - it would render two mouths")

    if mouth_mode == "viseme-track":
        frames, mouth_meta = mouth_track(timeline_payload["events"], fps, coarticulation)
    else:
        count = max(1, int(round(duration * fps)))
        frames = [{"frame": index, "time": round(index / fps, 4), "layers": []}
                  for index in range(count)]
        mouth_meta = {"absorbed": [], "extended": [], "closures": [],
                      "events_after_absorption": 0,
                      "note": "state mouth is static - the expression carries its own "
                              "mouth and no viseme track is applied (ADR-015)"}

    seed = int(timeline_payload.get("digest", "0")[:16] or "0", 16)
    tracks = secondary_tracks(duration, fps, seed, timeline_payload["events"],
                              secondary, idle)
    tracks["mouth"] = frames
    tracks["expression"] = segments
    tracks["brow"] = brow_track(segments, secondary)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": "8",
        "character": character,
        "state": state_name,
        "mouth_mode": mouth_mode,
        "fps": fps,
        "duration": round(duration, 3),
        "frame_count": len(frames),
        "pose": state.get("pose"),
        "camera_class": state.get("camera_class"),
        "idle_viseme": idle if mouth_mode == "viseme-track" else None,
        "source_timeline": {
            "digest": timeline_payload.get("digest"),
            "text": timeline_payload.get("text"),
            "timing_source": timeline_payload.get("timing_source"),
            "audio": (timeline_payload.get("audio") or {}).get("path"),
        },
        "coarticulation": {
            "version": coarticulation.get("version"),
            "blend_ms": coarticulation["blend_ms"],
            "min_frames_on_screen": coarticulation["min_frames_on_screen"],
        },
        "secondary": {"version": secondary.get("version"), "seed": seed},
        "mouth_meta": mouth_meta,
        "tracks": tracks,
    }
    payload["generated"] = generated
    payload["digest"] = digest(payload)
    return payload


def write(payload, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path
