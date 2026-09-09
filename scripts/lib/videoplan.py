"""The video plan: one document describing a finished video (PHASE 9).

PHASE 8 separated the frame plan from the render because a plan is inspectable,
diffable, and cheap to reject, while a render is none of those (ADR-024). The same
argument applies one layer up, and harder: a video costs an encode, and the things
that go wrong in it - a subtitle that outruns its audio, a push-in that upscales, a
camera crossing a framing class - are all decidable from the numbers.

So this assembles a plan and nothing else. It reads a PHASE 8 frame plan, a PHASE 7
timeline, a camera move, and a subtitle style, and produces a document that any
renderer can consume: ffmpeg today, HyperFrames when it exists, with the sampled
camera frames as the shared contract between them (ADR-032).
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import camera as camera_lib                           # noqa: E402
import subtitle as subtitle_lib                       # noqa: E402

DOCS = Path(__file__).resolve().parents[2] / "docs" / "video"
DEFAULT_RENDER_PROFILE = DOCS / "render-profile.json"

SCHEMA_VERSION = "1.0"

_CACHE = {}


class VideoPlanError(Exception):
    """The inputs cannot produce a coherent plan."""


def load_profiles(path=None):
    path = Path(path or DEFAULT_RENDER_PROFILE)
    key = str(path)
    if key not in _CACHE:
        try:
            _CACHE[key] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise VideoPlanError(f"cannot read render profile {path}: {error}") from error
    return _CACHE[key]


def resolve_profile(name=None, profiles=None):
    profiles = profiles or load_profiles()
    name = name or profiles["default_profile"]
    if name not in profiles["profiles"]:
        available = ", ".join(profiles["profiles"])
        raise VideoPlanError(f"unknown render profile {name!r} - have {available}")
    return name, dict(profiles["profiles"][name])


def digest(payload):
    """Stable hash of the plan; the timestamp is excluded, as in PHASE 7 and 8."""
    material = {
        "canvas": payload.get("canvas"),
        "camera": (payload.get("camera") or {}).get("frames"),
        "cues": [(cue["start"], cue["end"], cue["text"])
                 for cue in (payload.get("subtitles") or {}).get("cues", [])],
        "source_animation": (payload.get("source_animation") or {}).get("digest"),
        "render": payload.get("render"),
        "layers": payload.get("layers"),
    }
    blob = json.dumps(material, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _even(value):
    """Encoders reject odd dimensions under 4:2:0. Round down, never up."""
    return int(value) - (int(value) % 2)


def build(animation, timeline=None, move=None, profile=None, canvas=None,
          subtitles=True, subtitle_format=None, burn_in=False, broll=None,
          name=None, character="narra", camera_model=None, subtitle_style=None,
          generated=None):
    """Assemble a video plan from a PHASE 8 frame plan and its PHASE 7 timeline."""
    camera_model = camera_model or camera_lib.load_model()
    profiles = load_profiles()
    profile_name, render = resolve_profile(profile, profiles)

    fps = animation.get("fps")
    frame_count = animation.get("frame_count")
    duration = animation.get("duration")
    if not fps or not frame_count:
        raise VideoPlanError("the animation plan records no fps or frame_count - "
                             "a video cannot be timed against it")

    width = _even((canvas or {}).get("width", camera_model["canvas"]["width"]))
    height = _even((canvas or {}).get("height", camera_model["canvas"]["height"]))
    if width <= 0 or height <= 0:
        raise VideoPlanError(f"canvas {width}x{height} is not renderable")

    camera_track = camera_lib.track(move, frame_count, fps, camera_model)

    cues, style = [], subtitle_lib.load_style(subtitle_style)
    if subtitles:
        if timeline is None:
            raise VideoPlanError(
                "subtitles were asked for but no timeline was given - the cue text and "
                "its word boundaries come from the PHASE 7 parse, not from the frame "
                "plan, which carries no text")
        cues = subtitle_lib.cues(timeline, style)

    layers = []
    if broll:
        layers.append({"kind": "broll", "z": 0, "segments": list(broll)})
    layers.append({"kind": "avatar", "z": 10,
                   "source_resolution": camera_model["avatar"]["source_resolution"],
                   "height_fraction": camera_model["avatar"]["height_fraction"],
                   "anchor": camera_model["avatar"]["anchor"]})
    if cues:
        layers.append({"kind": "subtitle", "z": 20,
                       "burn_in": bool(burn_in),
                       "position": style["style"]["position"]})

    source_timeline = animation.get("source_timeline") or {}
    audio_path = source_timeline.get("audio")
    audio = {"path": audio_path}
    if timeline and timeline.get("audio"):
        audio = {"path": timeline["audio"].get("path", audio_path),
                 "sha256": timeline["audio"].get("sha256"),
                 "duration": timeline["audio"].get("duration"),
                 "sample_rate": timeline["audio"].get("sample_rate")}

    payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": "9",
        "character": animation.get("character", character),
        "name": name or "video",
        "canvas": {"width": width, "height": height, "fps": fps,
                   "background": camera_model["canvas"]["background"]},
        "duration": duration,
        "frame_count": frame_count,
        "source_animation": {
            "digest": animation.get("digest"),
            "state": animation.get("state"),
            "mouth_mode": animation.get("mouth_mode"),
            "pose": animation.get("pose"),
            "camera_class": animation.get("camera_class"),
            "fps": fps,
            "frame_count": frame_count,
        },
        "source_timeline": {
            "digest": source_timeline.get("digest"),
            "text": source_timeline.get("text"),
            "timing_source": source_timeline.get("timing_source"),
        },
        "audio": audio,
        "layers": layers,
        "camera": camera_track,
        "subtitles": {
            "language": style.get("language", "th"),
            "format": subtitle_format or style["output"]["default_format"],
            "style_version": style.get("version"),
            "burn_in": bool(burn_in),
            "cue_count": len(cues),
            "cues": cues,
        },
        "broll": list(broll or []),
        "render": dict(render, profile=profile_name,
                       engine=profiles["engines"]["default"]),
        "generated": generated or datetime.now(timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    payload["digest"] = digest(payload)
    return payload


def write(payload, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VideoPlanError(f"cannot read video plan {path}: {error}") from error
