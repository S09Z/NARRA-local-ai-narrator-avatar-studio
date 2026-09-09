"""Thai subtitle cues from a PHASE 7 timeline (PHASE 9).

Thai is written without spaces between words. Wrapping it at a character count is
not a cosmetic compromise the way it is in English - it splits words, orphans final
consonants, and can separate a vowel or tone mark from the consonant it sits on,
which is not a bad line break but a different string. So cues are built out of the
segmentation PHASE 7 already computed, and break only where a word ends (ADR-033).

The timeline records the text, the G2P engine, and the syllable count; the syllables
themselves are not stored, so they are re-derived and the count is checked. A
mismatch means the parse changed under the timeline, and this refuses rather than
subtitling a sentence with somebody else's word boundaries.

What this module does not do is draw anything. Cues are timed text; painting them
into pixels needs a shaping engine and is a separate decision (ADR-035).
"""

import json
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import thai_g2p                                       # noqa: E402

DOCS = Path(__file__).resolve().parents[2] / "docs" / "video"
DEFAULT_STYLE = DOCS / "subtitle-style.json"

SCHEMA_VERSION = "1.0"

_CACHE = {}


class SubtitleError(Exception):
    """The timeline and its text disagree, or a cue cannot be built from them."""


def load_style(path=None):
    path = Path(path or DEFAULT_STYLE)
    key = str(path)
    if key not in _CACHE:
        try:
            _CACHE[key] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SubtitleError(f"cannot read subtitle style {path}: {error}") from error
    return _CACHE[key]


# --- words ----------------------------------------------------------------------

def _syllable_times(payload):
    """Syllable index -> (start, end), read off the timeline's events."""
    times = {}
    for event in payload.get("events", []):
        index = event.get("syllable")
        if index is None:
            continue
        start, end = times.get(index, (event["start"], event["end"]))
        times[index] = (min(start, event["start"]), max(end, event["end"]))
    return times


def words(payload, engine=None):
    """The timeline's text as timed words, in order.

    A word here is one orthographic span the parser claimed - which is a lexicon
    entry or a single pattern match, not a linguistic word. That is the unit a line
    may break between, and it is the finest one available without a dictionary.
    """
    text = payload.get("text")
    if not text:
        raise SubtitleError("the timeline records no text")

    engine = engine or (payload.get("g2p") or {}).get("engine")
    engine = None if engine == "builtin" else engine
    result = thai_g2p.phonemize(text, engine)

    recorded = (payload.get("g2p") or {}).get("syllables")
    if recorded is not None and recorded != len(result.syllables):
        raise SubtitleError(
            f"the timeline records {recorded} syllables, re-parsing gives "
            f"{len(result.syllables)} - the parse changed under this timeline, so its "
            "times and these word boundaries are not describing the same sentence")

    normalised, source, base = thai_g2p.normalise_map(text)
    times = _syllable_times(payload)
    pause_after = set(result.breaks)

    out = []
    for syllable in result.syllables:
        if syllable.span is None:
            raise SubtitleError(
                f"G2P engine {engine or 'builtin'} returned a syllable with no span; "
                "subtitle line breaking needs one (thai_g2p.Syllable.span)")
        span = thai_g2p.base_span(syllable.span, source, base)
        window = times.get(syllable.index)
        if out and out[-1]["span"] == span:
            entry = out[-1]
            entry["syllables"].append(syllable.index)
        else:
            entry = {"span": span, "text": base[span[0]:span[1]],
                     "syllables": [syllable.index], "start": None, "end": None}
            out.append(entry)
        if window:
            entry["start"] = window[0] if entry["start"] is None else min(entry["start"],
                                                                         window[0])
            entry["end"] = window[1] if entry["end"] is None else max(entry["end"],
                                                                      window[1])
        entry["pause_after"] = syllable.index in pause_after

    return _fill_gaps(out, payload)


def _fill_gaps(entries, payload):
    """A word whose syllables produced no event still has to appear and be timed.

    It borrows the boundary of its neighbours rather than being dropped: a missing
    word in a subtitle is a worse failure than a slightly early one.
    """
    duration = payload.get("duration") or 0.0
    for index, entry in enumerate(entries):
        if entry["start"] is not None and entry["end"] is not None:
            continue
        before = next((entries[i]["end"] for i in range(index - 1, -1, -1)
                       if entries[i]["end"] is not None), 0.0)
        after = next((entries[i]["start"] for i in range(index + 1, len(entries))
                      if entries[i]["start"] is not None), duration)
        entry["start"] = entry["start"] if entry["start"] is not None else before
        entry["end"] = entry["end"] if entry["end"] is not None else max(after, before)
    return entries


# --- lines ----------------------------------------------------------------------

def _width(text):
    """Characters a reader sees. Combining marks stack; they do not take width."""
    return sum(1 for ch in text if not unicodedata.combining(ch))


def _line_text(base, group):
    return base[group[0]["span"][0]:group[-1]["span"][1]].strip()


def _wrap(group, base, max_lines, max_chars):
    """Break one cue's words into lines, or return None if it will not fit.

    Two lines are split as evenly as the words allow. A subtitle with eleven
    characters on the second line reads as a mistake even when it is legal.
    """
    if not group:
        return []
    whole = _line_text(base, group)
    if _width(whole) <= max_chars:
        return [whole]
    if max_lines < 2:
        return None

    if max_lines == 2:
        best = None
        for split in range(1, len(group)):
            first = _line_text(base, group[:split])
            second = _line_text(base, group[split:])
            widths = (_width(first), _width(second))
            if max(widths) > max_chars:
                continue
            score = abs(widths[0] - widths[1])
            if best is None or score < best[0]:
                best = (score, [first, second])
        return best[1] if best else None

    lines, current = [], []
    for word in group:
        candidate = current + [word]
        if _width(_line_text(base, candidate)) > max_chars and current:
            lines.append(_line_text(base, current))
            current = [word]
        else:
            current = candidate
    if current:
        lines.append(_line_text(base, current))
    return lines if len(lines) <= max_lines else None


# --- cues -----------------------------------------------------------------------

def cues(payload, style=None, engine=None):
    """Timed, line-broken subtitle cues covering the timeline's text."""
    style = style or load_style()
    layout = style["layout"]
    reading = style["reading"]
    max_lines = layout["max_lines"]
    max_chars = layout["max_characters_per_line"]

    entries = words(payload, engine)
    if not entries:
        return []
    _, _, base = thai_g2p.normalise_map(payload["text"])

    groups, current = [], []
    for entry in entries:
        candidate = current + [entry]
        span_seconds = candidate[-1]["end"] - candidate[0]["start"]
        wrapped = _wrap(candidate, base, max_lines, max_chars)
        too_long = span_seconds > reading["max_duration_s"]
        if current and (wrapped is None or too_long):
            groups.append(current)
            current = [entry]
        else:
            current = candidate
        if current and current[-1].get("pause_after") and \
                _wrap(current, base, max_lines, max_chars) is not None:
            groups.append(current)
            current = []
    if current:
        groups.append(current)

    built = []
    for index, group in enumerate(groups):
        lines = _wrap(group, base, max_lines, max_chars)
        if lines is None:                              # one word wider than a line
            lines = [_line_text(base, group)[:max_chars]]
        text = "\n".join(lines)
        built.append({
            "index": index + 1,
            "start": round(group[0]["start"], 3),
            "end": round(group[-1]["end"], 3),
            "lines": lines,
            "text": text,
            "characters": _width(text.replace("\n", "")),
            "words": len(group),
            "syllables": [i for word in group for i in word["syllables"]],
        })

    return _retime(built, reading, payload.get("duration"))


def _retime(built, reading, duration):
    """Hold short cues long enough to read, without letting them collide.

    A cue cannot be extended past the next one minus the minimum gap, and cannot run
    past the audio. Where the words are simply spoken faster than the reading speed,
    that is recorded on the cue rather than fixed - the fix is a shorter script, and
    a subtitle that lies about its own timing helps nobody.
    """
    minimum = reading["min_duration_s"]
    gap = reading["min_gap_s"]
    limit = duration if duration else None

    for index, cue in enumerate(built):
        if cue["end"] - cue["start"] >= minimum:
            continue
        ceiling = built[index + 1]["start"] - gap if index + 1 < len(built) else limit
        wanted = cue["start"] + minimum
        cue["end"] = round(wanted if ceiling is None else min(wanted, ceiling), 3)

    for cue in built:
        seconds = max(cue["end"] - cue["start"], 0.001)
        cue["duration"] = round(seconds, 3)
        cue["reading_speed_cps"] = round(cue["characters"] / seconds, 1)
        cue["too_fast"] = cue["reading_speed_cps"] > reading["characters_per_second"]
        cue["too_short"] = seconds + 0.0005 < minimum
    return built


# --- serialisation ---------------------------------------------------------------

def _srt_time(seconds):
    milli = int(round(seconds * 1000))
    hours, milli = divmod(milli, 3600000)
    minutes, milli = divmod(milli, 60000)
    secs, milli = divmod(milli, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milli:03d}"


def _ass_time(seconds):
    centi = int(round(seconds * 100))
    hours, centi = divmod(centi, 360000)
    minutes, centi = divmod(centi, 6000)
    secs, centi = divmod(centi, 100)
    return f"{hours:d}:{minutes:02d}:{secs:02d}.{centi:02d}"


def to_srt(built):
    """SubRip. Universally readable, and the format a reviewer can open and correct."""
    blocks = []
    for cue in built:
        blocks.append(f"{cue['index']}\n"
                      f"{_srt_time(cue['start'])} --> {_srt_time(cue['end'])}\n"
                      f"{cue['text']}\n")
    return "\n".join(blocks)


def to_ass(built, style=None, canvas=None):
    """Advanced SubStation Alpha, for burn-in through ffmpeg's libass.

    libass shapes Thai through HarfBuzz, which is the reason this format exists here
    rather than painting the glyphs directly (ADR-035).
    """
    style = style or load_style()
    look = style["style"]
    width = (canvas or {}).get("width", 1920)
    height = (canvas or {}).get("height", 1080)
    size = int(round(height * look["size_fraction_of_height"]))
    margin = int(round(height * look["safe_area_fraction"]))
    family = look["font_family"][0]

    def colour(value):                                 # #RRGGBB -> &H00BBGGRR
        value = value.lstrip("#")
        return f"&H00{value[4:6]}{value[2:4]}{value[0:2]}"

    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 2",                                # honour our line breaks exactly
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, "
        "Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, "
        "MarginV, Encoding",
        f"Style: Narra,{family},{size},{colour(look['colour'])},"
        f"{colour(look['outline_colour'])},&H00000000,0,0,1,"
        f"{look['outline_width_px']},0,2,{margin},{margin},{margin},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for cue in built:
        text = cue["text"].replace("\n", "\\N")
        header.append(f"Dialogue: 0,{_ass_time(cue['start'])},{_ass_time(cue['end'])},"
                      f"Narra,,0,0,0,,{text}")
    return "\n".join(header) + "\n"


def find_font(style=None):
    """First configured font file that exists, or None. Never a silent substitute."""
    style = style or load_style()
    for candidate in style["style"]["font_files"]:
        if Path(candidate).exists():
            return candidate
    return None
