"""Camera framing and motion over rendered avatar frames (PHASE 9).

A camera here reframes pixels that already exist. It cannot generate detail, which
is the whole of its discipline: a push-in past the point where one source pixel
covers more than one output pixel is not a camera move, it is an upscale wearing
one. The limits in docs/video/camera-model.json are that rule and its neighbours,
and `check_limits` is where a plan is held to them (ADR-034).

Motion is emitted twice. `keyframes` carry the authoring intent with GSAP easing
names, so a GSAP renderer can reproduce the curve rather than approximate it.
`frames` carry the curve already sampled, one entry per frame, and those are what a
renderer must draw - two renderers agreeing on the sampled values is the only way
ffmpeg and a browser produce the same motion (ADR-032).
"""

import json
import math
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs" / "video"
DEFAULT_MODEL = DOCS / "camera-model.json"

SCHEMA_VERSION = "1.0"

_CACHE = {}


class CameraError(Exception):
    """A move that cannot be resolved, or keyframes that do not describe a curve."""


def load_model(path=None):
    path = Path(path or DEFAULT_MODEL)
    key = str(path)
    if key not in _CACHE:
        try:
            _CACHE[key] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CameraError(f"cannot read camera model {path}: {error}") from error
    return _CACHE[key]


# --- easing ---------------------------------------------------------------------
# GSAP's power1/2/3 are quadratic, cubic, quartic. Matching the exponents matters:
# a curve that is close but not equal makes a browser render and an ffmpeg render
# disagree by a few pixels a frame, which reads as judder rather than as a bug.

_POWERS = {"power1": 2, "power2": 3, "power3": 4}


def easing(name):
    """A GSAP easing name as a function on [0, 1]."""
    if not name or name == "none" or name == "linear":
        return lambda t: t

    family, _, direction = name.partition(".")
    direction = direction or "out"

    if family == "sine":
        curves = {
            "in": lambda t: 1 - math.cos(t * math.pi / 2),
            "out": lambda t: math.sin(t * math.pi / 2),
            "inOut": lambda t: -(math.cos(math.pi * t) - 1) / 2,
        }
    elif family in _POWERS:
        power = _POWERS[family]
        curves = {
            "in": lambda t, p=power: t ** p,
            "out": lambda t, p=power: 1 - (1 - t) ** p,
            "inOut": lambda t, p=power: (2 ** (p - 1)) * t ** p if t < 0.5
            else 1 - (-2 * t + 2) ** p / 2,
        }
    else:
        raise CameraError(f"unknown easing {name!r}")

    if direction not in curves:
        raise CameraError(f"unknown easing direction in {name!r}")
    return curves[direction]


def supported_easings(model=None):
    return list((model or load_model())["easing"]["supported"])


# --- moves ----------------------------------------------------------------------

def resolve_move(move, model=None):
    """A move name, or explicit keyframes, to a validated keyframe list."""
    model = model or load_model()
    if isinstance(move, dict) and "keyframes" in move:
        keyframes = move["keyframes"]
    elif isinstance(move, list):
        keyframes = move
    else:
        name = move or model["default_move"]
        if name not in model["moves"] or name.startswith("$"):
            available = ", ".join(k for k in model["moves"] if not k.startswith("$"))
            raise CameraError(f"unknown camera move {name!r} - have {available}")
        keyframes = model["moves"][name]["keyframes"]

    if not keyframes:
        raise CameraError("a camera move needs at least one keyframe")

    resolved = []
    for frame in keyframes:
        entry = {"t": float(frame.get("t", 0.0)),
                 "scale": float(frame.get("scale", 1.0)),
                 "x": float(frame.get("x", 0.0)),
                 "y": float(frame.get("y", 0.0)),
                 "ease": frame.get("ease") or model["easing"]["default"]}
        if not 0.0 <= entry["t"] <= 1.0:
            raise CameraError(f"keyframe t={entry['t']} is outside [0, 1]")
        easing(entry["ease"])                          # raises on an unknown name
        resolved.append(entry)

    resolved.sort(key=lambda entry: entry["t"])
    if any(a["t"] == b["t"] for a, b in zip(resolved, resolved[1:])):
        raise CameraError("two camera keyframes share the same t")
    return resolved


def sample(keyframes, frame_count, fps):
    """The curve evaluated once per frame - what a renderer actually draws."""
    if frame_count <= 0:
        return []
    out = []
    for index in range(frame_count):
        position = index / (frame_count - 1) if frame_count > 1 else 0.0
        out.append({"frame": index,
                    "time": round(index / fps, 4) if fps else 0.0,
                    **_at(keyframes, position)})
    return out


def _at(keyframes, position):
    if position <= keyframes[0]["t"]:
        first = keyframes[0]
        return {"scale": round(first["scale"], 6), "x": round(first["x"], 6),
                "y": round(first["y"], 6)}
    if position >= keyframes[-1]["t"]:
        last = keyframes[-1]
        return {"scale": round(last["scale"], 6), "x": round(last["x"], 6),
                "y": round(last["y"], 6)}

    for start, end in zip(keyframes, keyframes[1:]):
        if start["t"] <= position <= end["t"]:
            span = end["t"] - start["t"]
            local = (position - start["t"]) / span if span else 0.0
            # GSAP applies the ease of the keyframe a tween starts from.
            eased = easing(start["ease"])(local)
            return {key: round(start[key] + (end[key] - start[key]) * eased, 6)
                    for key in ("scale", "x", "y")}
    last = keyframes[-1]                               # unreachable while t is sorted
    return {"scale": last["scale"], "x": last["x"], "y": last["y"]}


def track(move, frame_count, fps, model=None):
    """The complete camera track for a plan: intent, easing names, sampled frames."""
    model = model or load_model()
    keyframes = resolve_move(move, model)
    name = move if isinstance(move, str) else "custom"
    return {"move": name or model["default_move"],
            "keyframes": keyframes,
            "easing_vocabulary": "gsap",
            "authoritative": "frames",
            "frames": sample(keyframes, frame_count, fps)}


# --- limits ---------------------------------------------------------------------

def drawn_height(scale, model=None):
    """Output pixels the avatar occupies vertically at this scale."""
    model = model or load_model()
    return model["canvas"]["height"] * model["avatar"]["height_fraction"] * scale


def sampling_ratio(scale, model=None):
    """Output pixels per source pixel. Above 1.0 the renderer is inventing detail."""
    model = model or load_model()
    return drawn_height(scale, model) / model["avatar"]["source_resolution"]


def class_scale_limit(camera_class, model=None):
    """The scale at which this class's framing reaches close-up framing.

    A three-quarter pose was rendered with a head 0.48 the height of a close-up one.
    Pushing past 1/0.48 asks it to stand in for a close-up it has no detail for.
    """
    model = model or load_model()
    ratio = model["class_ratios"].get(camera_class)
    if not ratio:
        return None
    return 1.0 / ratio


def check_limits(camera_track, camera_class=None, duration=None, model=None):
    """Findings against the model's limits, as (level, name, detail) triples."""
    model = model or load_model()
    limits = model["limits"]
    frames = camera_track.get("frames") or []
    findings = []
    if not frames:
        return [("FAIL", "camera/frames", "the camera track has no sampled frames")]

    scales = [frame["scale"] for frame in frames]
    peak = max(scales)
    if peak > limits["max_scale"]:
        findings.append(("FAIL", "camera/scale",
                         f"peak scale {peak:.3f} exceeds max_scale "
                         f"{limits['max_scale']}"))
    elif min(scales) < limits["min_scale"]:
        findings.append(("FAIL", "camera/scale",
                         f"minimum scale {min(scales):.3f} is below min_scale "
                         f"{limits['min_scale']}"))
    else:
        findings.append(("PASS", "camera/scale", f"{min(scales):.3f}..{peak:.3f}"))

    ratio = sampling_ratio(peak, model)
    if ratio > limits["max_sampling_ratio"]:
        findings.append(("WARN", "camera/resolution",
                         f"at peak scale the avatar draws at "
                         f"{drawn_height(peak, model):.0f}px from a "
                         f"{model['avatar']['source_resolution']}px source "
                         f"({ratio:.2f} output px per source px) - past 1.0 the push-in "
                         "is an upscale"))
    else:
        findings.append(("PASS", "camera/resolution",
                         f"{ratio:.2f} output px per source px at peak scale"))

    if camera_class:
        ceiling = class_scale_limit(camera_class, model)
        if ceiling is None:
            findings.append(("WARN", "camera/class",
                             f"no class ratio recorded for {camera_class!r}"))
        elif peak > ceiling:
            findings.append(("WARN", "camera/class",
                             f"scale {peak:.3f} on a {camera_class} asset takes the head "
                             f"past close-up framing (from {ceiling:.3f}) - no generated "
                             "asset shows this character that large, so nothing here was "
                             "ever checked at this size"))
        else:
            findings.append(("PASS", "camera/class",
                             f"{camera_class}, peak {peak:.3f} of {ceiling:.3f}"))

    if duration and duration > 0:
        scale_rate = (peak - min(scales)) / duration
        if scale_rate > limits["max_scale_change_per_second"]:
            findings.append(("WARN", "camera/speed",
                             f"scale changes {scale_rate:.3f}/s, over "
                             f"{limits['max_scale_change_per_second']}/s - a narration "
                             "camera that moves this fast reads as an effect"))
        else:
            findings.append(("PASS", "camera/speed", f"{scale_rate:.3f} scale/s"))

        pan = max(max(abs(frame["x"]) for frame in frames),
                  max(abs(frame["y"]) for frame in frames))
        if pan > limits["max_pan_fraction"]:
            findings.append(("FAIL", "camera/pan",
                             f"pan reaches {pan:.3f} of the frame, over "
                             f"{limits['max_pan_fraction']}"))
        else:
            findings.append(("PASS", "camera/pan", f"{pan:.3f} of the frame"))

    return findings
