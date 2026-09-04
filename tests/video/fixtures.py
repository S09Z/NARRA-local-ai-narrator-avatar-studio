"""Real PHASE 7 and PHASE 8 payloads for the PHASE 9 tests.

Built by running the actual pipeline rather than by hand-writing JSON: a fixture
that drifts from what build_timeline.py and build_animation.py produce would test
PHASE 9 against a document nothing generates.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "lib"))

import animation as animation_lib                     # noqa: E402
import thai_g2p                                       # noqa: E402
import timeline as timeline_lib                       # noqa: E402

SENTENCE = "สวัสดีครับ วันนี้เราจะมาเรียนรู้เรื่องการทำอาหารไทย"
STATE = {"expression": "neutral", "pose": "neutral", "mouth": "viseme-track",
         "camera_class": "medium", "idle_viseme": "REST"}


AUDIO = {"path": "/tmp/narra-fixture.wav", "sha256": "0" * 64, "duration": 4.73,
         "sample_rate": 22050, "channels": 1}


def timeline(text=SENTENCE, duration=4.73, audio=None):
    """A timeline that carries an audio record, as every real one does.

    The path need not exist - what depends on it is the plan's shape, and what
    depends on the file is probed separately by render_video.probe.
    """
    result = thai_g2p.phonemize(text)
    audio = dict(AUDIO, duration=duration) if audio is None else audio
    payload = timeline_lib.build(result, audio_duration=duration, audio=audio)
    payload["digest"] = timeline_lib.digest(payload)
    return payload


def animation(timeline_payload=None, fps=25, state=None):
    timeline_payload = timeline_payload or timeline()
    return animation_lib.build(timeline_payload, state or STATE, "talking", fps)
