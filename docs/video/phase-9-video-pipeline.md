# PHASE 9 — Video Pipeline

Frame plan + audio + subtitles + camera → a video plan → MP4.

PLAN §9 asks for HyperFrames as the compositor, timeline engine, subtitle renderer,
camera and final renderer, with GSAP driving the transitions. What is built here is
the artefact all of that consumes — a complete, validated, renderer-independent plan —
plus one reference renderer that turns it into an MP4 today. Why it is split that way
is `DECISIONS.md` → ADR-032.

---

## 0. Gate status — read first

**The PHASE 6 image gate has not passed.** 0 of 38 character assets exist. PHASE 7 and
PHASE 8 were built ahead of it on explicit instruction (ADR-023, ADR-027) and this is
the third time (ADR-036).

What that costs here, precisely:

| Stage | State |
|-------|-------|
| Video plan | fully exercised — plans build and validate against real timelines and frame plans |
| Camera | fully exercised — sampling and limits are pure arithmetic |
| Subtitles | fully exercised — cues come from a real Thai parse |
| Scene compositing | exercised against **synthetic** PNGs only |
| Encoding | **never run** — ffmpeg is not installed on the development machine |

No frame of this pipeline has ever been composited from a real narrator asset, and no
MP4 has ever been produced. `render_video.py --check` reports exactly that, per
requirement, rather than failing partway through an encode.

---

## 1. Quick start

```bash
# Thai text -> timeline -> frame plan (PHASE 7 and 8)
python3 scripts/audio/build_timeline.py "สวัสดีครับ" --tts --name greeting
python3 scripts/animation/build_animation.py \
        metadata/timelines/greeting-timeline-v1.json --fps 25 --name greeting

# frame plan -> video plan + subtitle sidecar (PHASE 9)
python3 scripts/video/build_video.py \
        metadata/animations/greeting-animation-v1.json --move slow-push

# check the plan before spending an encode on it
python3 scripts/validation/validate_video.py metadata/videos/greeting-video-v1.json

# what would a render need? (decodes nothing)
python3 scripts/video/render_video.py metadata/videos/greeting-video-v1.json --check

# render (needs PHASE 8 frames, which need the image library, and ffmpeg)
python3 scripts/video/render_video.py metadata/videos/greeting-video-v1.json
```

`--report` on `build_video.py` prints the plan and writes nothing. `--print-command`
on `render_video.py` prints the exact ffmpeg call without running it.

---

## 2. The plan is the artefact (ADR-032)

PHASE 8 separated the frame plan from the render because a plan is inspectable and a
render is not (ADR-024). One layer up the argument is stronger, because a video costs
an encode and everything that goes wrong in one is visible in the numbers first:

- a cue that outruns its audio is a subtitle over black
- two cues that overlap put two subtitles on screen
- a push-in past the source resolution is an upscale, not a camera move
- an odd canvas dimension is rejected by libx264 a minute into the encode

So `build_video.py` writes a document and `validate_video.py` judges it. Nothing is
encoded until both are satisfied.

### Why HyperFrames is declared and not wired up

`docs/video/render-profile.json` lists two engines. `ffmpeg` is implemented.
`hyperframes` is `"declared, not implemented"` and says why: the tool is not present
in this repository, so it cannot be inspected, version-pinned, or verified, and
`CLAUDE.md` requires all three before a dependency is added. GSAP additionally
implies a Node and browser runtime — a dependency surface larger than the whole
project, which currently runs on Pillow and pytest.

The plan is built so that adding it later is not a rewrite:

- camera motion carries **GSAP easing names** (`sine.inOut`, `power2.out`), so a GSAP
  renderer reproduces the curve rather than approximating it
- camera motion also carries the curve **already sampled, one entry per frame**, and
  the plan marks `"authoritative": "frames"` — two renderers agree because they read
  the same numbers, not because they happen to ease alike

---

## 3. Thai subtitles (ADR-033)

Thai is written without spaces between words. Wrapping it at a character count is not
the mild compromise it is in English:

```
เรียนรู้เรื่องการทำอาหาร     wrapped at 12 characters
เรียนรู้เรื่อ | งการทำอาหาร   splits a word, and orphans its final consonant
```

Worse, a break can land between a consonant and the vowel or tone mark sitting on it,
which does not produce an ugly line — it produces a different string.

Cues are therefore built from the segmentation PHASE 7 already computed. The timeline
records the text, the engine, and the syllable count; the syllables themselves are
re-derived and **the count is checked**. A mismatch means the parser changed under the
timeline, and `subtitle.py` refuses rather than subtitling a sentence with somebody
else's word boundaries.

### Getting the spelling back

Phonemization strips tone marks — tone does not change mouth shape (mapping.md §0) —
and deletes consonants silenced by thanthakhat. A subtitle has to show them:
`วันนี้`, not `วันนี`; `สตางค์`, not `สตาง`. `thai_g2p.normalise_map()` records where every
surviving character came from and `base_span()` walks back over what was removed, so
display text is exact. Both live beside the stripping rather than re-implementing it
against it (ADR-011).

### Timing

| Rule | Value | Where from |
|------|-------|-----------|
| Reading speed | 20 cps | Netflix Thai timed-text guide |
| Minimum on screen | 0.833 s | same |
| Maximum | 7 s | same |
| Minimum gap | 0.083 s | same |
| Lines × characters | 2 × 42 | same |

A cue shorter than the minimum is extended, but never past the next cue minus the gap
and never past the audio. Where the script is simply denser than the audio allows, the
cue is flagged `too_fast` and left alone — the fix is a shorter script, and a subtitle
that lies about its own timing helps nobody.

**These numbers are unreviewed by a Thai speaker.** So is the viseme mapping they sit
downstream of, outstanding since PHASE 4.2 and now three phases deep.

---

## 4. Subtitles are a sidecar, not pixels (ADR-035)

`build_video.py` writes `assets/video/<name>.srt` beside the plan. Burning the text
into the frames is off by default, and when it is on it goes through ffmpeg's libass —
never through Pillow.

Pillow shapes complex scripts only when built against Raqm. Without it, Thai tone
marks are positioned by glyph advance and land beside the consonant instead of above
it. The Pillow on this machine reports `raqm: False`, and a renderer that silently
produces mispositioned Thai is worse than one that refuses.

There is a second reason, unrelated to shaping: a sidecar can be read, corrected, and
reviewed by the Thai speaker this pipeline still needs. Burned-in text cannot be
changed without a re-render.

---

## 5. Camera (ADR-034)

A camera move reframes pixels that already exist. It cannot generate detail, and the
limits are that rule and its neighbours:

| Limit | Value | What it prevents |
|-------|-------|------------------|
| `max_sampling_ratio` | 1.0 | drawing one source pixel larger than one output pixel |
| `max_scale` / `min_scale` | 1.35 / 0.6 | a move that has stopped being a move |
| `max_scale_change_per_second` | 0.12 | a narration camera that reads as an effect |
| `max_pan_fraction` | 0.25 | panning the character out of frame |
| class ceiling | `1 / class_ratio` | pushing a wide pose into close-up framing |

The class ceiling comes from `visual-spec.md` §2 (ADR-014). A `three-quarter` pose was
rendered with a head 0.48 the height of a close-up one; scaling past `1/0.48` asks it
to stand in for a close-up whose detail was never generated. That is a **warning**, not
a failure — no generated asset shows the character that large, so nothing at that size
was ever checked, but framing is a creative call. The numeric limits are the hard ones.

Shipped moves: `static` (the default, and correct for most narration), `slow-push`,
`slow-pull`, `settle`, `drift-left`. Every one of them is tested against the limits
the same file declares.

---

## 6. What the validator enforces

```
canvas/size          even dimensions; libx264 rejects odd ones under 4:2:0
canvas/fps           equal to the frame plan's, or the lip-sync drifts against its audio
canvas/duration      frame_count / fps agrees with the recorded duration
layers/avatar        something to render
camera/frames        one sample per video frame
camera/easing        names inside the GSAP vocabulary
camera/*             the limits in §5
subtitle/order       every cue moves forward
subtitle/overlap     never two subtitles on screen
subtitle/bounds      no cue past the audio
subtitle/layout      within lines x characters
subtitle/burn-in     burn-in implies .ass, because libass needs it
render/engine        the engine is implemented, not merely declared
render/pixel-format  yuv420p, or it will not play everywhere
source/animation     the frame plan digest, so a video traces to its lip-sync
lock/digest          the plan has not been edited since it was generated
```

`--strict` turns warnings into failures. Warnings are where estimated timing, fast
cues, and upscaling live.

---

## 7. Files

```
scripts/lib/subtitle.py                   Thai cue building and serialisation
scripts/lib/camera.py                     easing, sampling, limits
scripts/lib/videoplan.py                  plan assembly and digest
scripts/video/build_video.py              frame plan -> video plan + sidecar
scripts/video/render_video.py             video plan -> scene frames -> MP4
scripts/validation/validate_video.py      video plan QC

docs/video/subtitle-style.json            Thai timing, layout, and style
docs/video/camera-model.json              canvas, class ratios, limits, moves
docs/video/render-profile.json            encoder profiles and the engine registry

metadata/videos/                          generated video plans (gitignored)
assets/video/                             sidecars, scene frames, MP4s (gitignored)
```

`thai_g2p.py` gained `Syllable.span`, `normalise_map()`, and `base_span()` for §3.

---

## 8. Before PHASE 10

- [ ] **Pass the PHASE 6 gate.** Three phases now depend on assets that do not exist.
- [ ] Install ffmpeg and encode one clip end to end. Nothing here has produced an MP4.
- [ ] Get the Thai viseme mapping *and* the subtitle timing reviewed by a Thai speaker.
      Outstanding since PHASE 4.2, and now the reading-speed numbers depend on it too.
- [ ] Watch a real render and re-tune the camera limits. `max_sampling_ratio` is
      principled; `max_scale_change_per_second` is a judgement made without footage.
- [ ] Decide the b-roll question. The plan carries a `broll` track and the renderer
      composites nothing into it — there are no b-roll assets and no source for them.
- [ ] Confirm the canvas. 1920x1080 with a 1:1 avatar leaves a large empty frame;
      whether that is filled with b-roll, a lower third, or a square canvas instead is
      a design decision nobody has made.
