# PHASE 8 — Lip-Sync Animation Engine

Status: **implemented and tested**, running ahead of the PHASE 6 image gate by explicit
instruction — the second such override. See "Gate status" below.

Deliverables, against `PLAN.md` §8:

| Step | Deliverable | Where |
|------|-------------|-------|
| 8.1 Mouth switching | timeline events quantised to frames | `scripts/lib/animation.py` |
| 8.2 Coarticulation | blended weights from previous/current/next | `animation.py`, `docs/animation/coarticulation-model.json` |
| 8.3 Expression layer | independent expression track | `animation.py` |
| 8.4 Secondary | blink, breath, head sway, brow | `animation.py`, `docs/animation/secondary-animation.json` |
| Compositing | expression + blended viseme mouth | `scripts/lib/compositor.py` |
| QC | frame-plan validation | `scripts/validation/validate_animation.py` |

---

## 0. Gate status — read this first

`lock_library.py` still reports **GATE FAILED, 8 blocking problems, 0 of 38 image
assets**. PHASE 7 was built ahead of that gate (ADR-023); PHASE 8 now sits on top of
PHASE 7, on the same instruction (ADR-027).

The cost is no longer the same as it was for PHASE 7, and it is worth being exact about
the difference:

- PHASE 7 was text and audio. It was **fully testable** — real Thai speech went in and a
  validated timeline came out.
- PHASE 8 is images. Its whole job is to composite viseme assets onto expression assets,
  and **there are no assets**. Every test here runs against synthetic PNGs generated in a
  temp directory.

What that proves and does not prove:

| Verified | Not verified |
|----------|--------------|
| The compositor changes the mouth region and nothing else | That a real viseme *looks* right on a real expression |
| Weights blend proportionally and order-independently | That the blend of two real mouths reads as a mouth moving |
| Closures reach full weight; finals do not release early | That any of it looks like Thai speech |
| Every plan validates against 23 structural checks | Anything at all about the actual character |

`mapping.md` §6 names the first real test as the PHASE 8 lip-sync pass. That pass has
still not happened. It cannot happen until the assets exist.

---

## 1. Quick start

```bash
# Thai text -> timeline -> frame plan, in one command
python3 scripts/animation/build_animation.py --text "สวัสดีครับ" --tts --name greeting

# or from an existing PHASE 7 timeline
python3 scripts/animation/build_animation.py metadata/timelines/greeting-timeline-v1.json \
    --state explaining --fps 30

# check the plan
python3 scripts/validation/validate_animation.py --all

# what would rendering need? (decodes nothing)
python3 scripts/animation/render_frames.py metadata/animations/greeting-animation-v1.json --check

# render (needs the image library and a measured anchor)
python3 scripts/animation/render_frames.py metadata/animations/greeting-animation-v1.json \
    --out-dir assets/frames/greeting --contact-sheet /tmp/sheet.png
```

`--check` before `--out-dir`, always. It lists every asset the plan needs and every one
that is missing, without decoding a file.

---

## 2. The plan is not the render (ADR-024)

`build_animation.py` writes JSON and touches no pixels. `render_frames.py` reads that
JSON and needs the whole image library.

This split is why PHASE 8 could be built and validated at all with no assets, but that is
a consequence, not the reason. The reason is that the plan is the reviewable artefact: it
can be diffed, validated, and inspected frame by frame, and a wrong plan is visible as
JSON rather than as a mouth that looks slightly off in a video.

`metadata/animations/*.json` is generated output and is gitignored, like timelines.

---

## 3. Mouth switching (8.1)

Timeline events → frames at `fps` (default 25).

**The flicker rule is restated in frames** (ADR-026). PHASE 7 enforced a 0.060s minimum
without knowing the frame rate; PHASE 8 knows it, and frames are what reach the eye. At
25fps, 0.060s is 1.5 frames — which can quantise to one, which is exactly the flicker
`mapping.md` §6 forbids. The rule here is `min_frames_on_screen: 2`.

A shape too brief to survive is absorbed into its longer neighbour, and **recorded** in
`mouth_meta.absorbed` rather than dropped quietly:

```
note: 4 viseme(s) absorbed as too brief to read at 25fps: U, KG, L, L
```

That output is worth reading. At 25fps, brief consonants genuinely disappear. Raising fps
keeps more of them; that is a real trade and the note is how you see it happening.

---

## 4. Coarticulation (8.2)

PLAN 8.2 asks for smooth transitions using previous/current/next. A generic crossfade
would satisfy the letter of that and get Thai wrong in three specific ways.
`docs/thai-viseme/thai-viseme-mapping.md` names all three (ADR-025).

### An unreleased final does not pop open

`mapping.md` §3: Thai final stops are unreleased — the mouth closes and holds. Animating
a release frame is called out there as *the most common way to make Thai lip-sync look
foreign*.

A symmetric crossfade would start opening the closure halfway through its own event. So
for an unreleased final the transition is pushed **entirely after** the boundary:

```
symmetric:   [--- MBP ---|--- KG ---]     opening starts before the closure ends
unreleased:  [--- MBP ----]--- KG ---]    the closure holds to its end
```

The test is on the *outgoing* phoneme, not any phoneme in the event. PHASE 7 may have
merged a final into the initial that follows it (`t̚+d`), and that initial really does
open into its vowel — suppressing that release would be wrong in the other direction.

### A closure must actually close

`mapping.md` §5: /b p pʰ m/ all collapse to `MBP`, and `CLAUDE.md` requires `MBP` to be
visually distinct from `REST`. A bilabial blended so hard it never reaches full weight is
not a softer /p/ — it is a different consonant.

So closures get two protections. They are **exempt from absorption**: a closure too brief
to show is extended by borrowing from a neighbour instead of being deleted. And they are
**pinned**: if blending has still eaten the closure, the frame nearest its centre is
forced to full weight and the fact is recorded.

In practice the window clamp alone prevents this — blends never exceed 90% of the shorter
neighbour — so pinning is a net rather than the mechanism. It is tested directly for that
reason.

### A rounded vowel starts early

`mapping.md` §6: /k/ before /u/ is already rounding. `U`, `O` and `AO` use a longer blend
(90ms rather than 60ms) weighted 70/30 towards the preceding consonant, so the lips begin
rounding before the vowel arrives.

### Everything else

Two layers maximum — three shapes blend to mud. Weights are normalised per frame and
eased with a smoothstep, because a linear crossfade reads mechanical on a mouth. Adjacent
events carrying the same shape are one hold: a shape cannot crossfade with itself.

---

## 5. Expression layer (8.3)

The expression track is independent of the mouth track — that is ADR-004's whole point,
and it is what makes 12 expressions and 16 visemes cover 192 combinations instead of
needing 192 assets.

Default is the narrator state's expression for the whole duration. An expression plan
overrides it per segment:

```json
[{"start": 0.0, "end": 1.2, "expression": "neutral"},
 {"start": 1.2, "end": 3.0, "expression": "happy"}]
```

**One hard limit.** `excited`, `surprised`, and `explaining` carry their own open mouths
(ASSET_SPEC §6, ADR-012). They cannot host a viseme track — compositing a viseme over an
already-open mouth renders two mouths. `build_animation.py` refuses:

```
error: expression surprised has an open mouth and cannot host a viseme track
       (DECISIONS.md ADR-012) - it would render two mouths
```

`validate_compositions.py` already enforced this for a static narrator state. It has to
hold over *time* as well, because an expression plan can put an open mouth under a track
mid-sentence — which is why the check is repeated here rather than assumed.

A state whose `mouth` is `static` (`reaction`, `emphasis`) suppresses the viseme track
entirely. The expression is carrying the mouth; there is nothing to composite.

---

## 6. Secondary animation (8.4)

Blink, breath, head sway, and brow — emitted as **normalized keyframe tracks, not asset
swaps** (ADR-026). The library has 12 full-face expressions and no eye, brow, or head
assets, so there is nothing to swap. PHASE 9 binds these tracks to GSAP transforms;
PHASE 8 decides only what moves and when.

All of it is **deterministic**, seeded from the source timeline's digest. The same
narration always blinks in the same places. The image pipeline locks a seed; idle motion
should not be looser than that.

Blinks are pulled towards `REST` spans — a blink lands more naturally in a pause than
mid-syllable.

### A gap this surfaced in ASSET_SPEC

Rendering a blink needs an **eye region**, and `ASSET_SPEC.md` does not define one. It
defines a mouth anchor and a mouth `edit_region` (§9) because the viseme layer needed
them, and nothing has needed an eye region until now.

This is recorded rather than worked around. `secondary-animation.json` carries a
`render_requires` note on the blink track, and the blink timings are emitted regardless —
the timing is a real animation decision and is worth having even before it can be
rendered. Closing the gap means either measuring an eye region in the same way §9
measures the mouth, or adding eye-state assets to the library. That is a PHASE 9 or
asset-spec decision, not one to make silently here.

---

## 7. Compositing

A frame is:

```
expression asset  +  weighted blend of the frame's viseme mouth regions
```

This works because ASSET_SPEC §7 guarantees a viseme differs from `REST` **only inside
the permitted edit region**. Everything outside that box is identical, so the mouth
region can be lifted from a viseme and placed onto any expression.

Blending happens on non-premultiplied RGBA, which is exact only where the region is fully
opaque. `check_region_opaque` verifies that per asset rather than assuming it, and warns
if an asset breaks the assumption.

**Rendering requires a measured mouth anchor** (PHASE 4.3). Without one there is no edit
region and no way to know where the mouth is. The renderer refuses and says how to fix it:

```
error: the mouth anchor is unmeasured, so there is no edit region and no way to know
       where the mouth is (PHASE 4.3). Measure it from the approved reference:
       python3 scripts/utilities/measure_anchor.py --box L T R B
```

Secondary tracks are **not baked** into rendered frames. Head sway and breath are
transforms and belong to PHASE 9's compositor, per PLAN §9's split of GSAP duties.

---

## 8. What the validator enforces

`validate_animation.py`, 23 checks:

- frames are sequential, on the fps grid, and match `frame_count`
- weights sum to 1.0, at most 2 layers, no shape blended with itself, all canonical
- no interior hold shorter than `min_frames_on_screen`
- every closure reaches full weight; none was dropped for want of a donor
- expression track is canonical, contiguous, and covers the duration
- no open-mouth expression under a viseme track
- blinks inside the duration; one breath sample per frame
- `digest` matches, so a hand-edited plan is detectable
- source timeline `estimated` → WARN

---

## 9. Files

```
scripts/lib/animation.py                  the engine (8.1-8.4)
scripts/lib/compositor.py                 expression + viseme compositing
scripts/animation/build_animation.py      timeline -> frame plan
scripts/animation/render_frames.py        frame plan -> PNG frames
scripts/validation/validate_animation.py  frame plan QC

docs/animation/coarticulation-model.json  blend rules and their sources
docs/animation/secondary-animation.json   blink/breath/sway/brow settings

metadata/animations/                      generated frame plans (gitignored)
assets/frames/                            rendered frames (gitignored)
```

---

## 10. Before PHASE 9

- [ ] **Pass the PHASE 6 gate.** Two phases now depend on assets that do not exist.
- [ ] Measure the mouth anchor (PHASE 4.3). Nothing renders without it.
- [ ] Watch a real lip-sync pass and tune `coarticulation-model.json` — `blend_ms`, the
      anticipatory window, and `min_frames_on_screen` are all estimates until something
      has been looked at.
- [ ] Decide the eye-region question in §6 before blink can render.
- [ ] Get the Thai viseme mapping reviewed by a Thai speaker. Still outstanding from
      PHASE 4.2, and now two phases deep.
- [ ] Confirm the frame rate. 25 is a default, not a decision — PLAN does not specify one.
