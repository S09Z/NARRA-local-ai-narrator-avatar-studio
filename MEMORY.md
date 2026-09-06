# MEMORY.md

# NARRA Project Memory

This file stores durable project decisions.

## Current Goal

Generate consistent narrator avatar images locally before implementing lip-sync video.

## Project Name

NARRA — Local AI Narrator Avatar Studio

## Hardware

- RTX 5070 12GB
- 32GB RAM

## Primary Model

FLUX.2 Klein 4B Distilled

## Quality Model

FLUX.2 Klein 4B Base

## Canonical Asset Targets

Expressions:
12

Thai Visemes:
16

Poses:
10

## Thai Viseme Set

REST, A, I, U, E, O, AE, AO, MBP, FV, TH, KG, S, SH, L, N

## Important Decisions

- Image generation is the first milestone.
- Video/lip-sync is blocked until image assets are production-locked.
- Prefer reference editing over full regeneration.
- Keep expression and viseme layers independent.
- Avoid unnecessary custom nodes.
- LoRA is optional and not part of the initial critical path.
- HyperFrames belongs to the later video/compositing phase.

## Current Status

Phase 0: runbook written (`docs/operations/phase-0-environment-setup.md`), NOT RUN —
no ComfyUI, no models, no GPU environment yet. Must run on the RTX 5070 machine.
Phase 1: scaffolding complete, blocked on inputs. GATE NOT PASSED.
Phase 2: prompt system complete, blocked on the same inputs.
Phase 3: prompts + QC tooling complete, no assets generated.
Phase 4: prompts + mapping + QC tooling complete, no assets generated.
Phase 5: prompts + camera classes + compositions complete, no assets generated.
Phase 6: gate + lock tooling complete, GATE NOT PASSED — 0/38 assets exist.
Phase 7: audio/phoneme pipeline complete and tested, built ahead of the
image gate by explicit instruction (ADR-023). Unvalidated against real
viseme assets, because none exist.
Phase 8: lip-sync engine complete and tested, built ahead of the image gate on
the same instruction (ADR-027). Tested only against synthetic assets - no real
viseme has ever been composited onto a real expression.
Phase 9–10: planned, blocked by image-generation gate.

### Phase 1 — Reference Avatar Foundation

| Step | Deliverable | Status |
|------|-------------|--------|
| 1.1 Import reference | `character/reference/` importer + spec checks | Ready — **awaiting the reference image** |
| 1.2 Character bible  | `character/bible/character-bible.md` | Structure complete — identity fields awaiting the reference image |
| 1.3 Visual spec      | `character/bible/visual-spec.md`, `mouth-anchor.json` | Structure complete — measurements awaiting the reference image |
| 1.4 Baseline tests   | `tests/assets/phase1-baseline.md` | Protocol written — **blocked on the PHASE 0 gate** |

Two inputs unblock the rest of Phase 1:

1. The canonical reference image (1024x1024 PNG RGBA, transparent background, neutral
   expression, REST mouth). Import with
   `python3 scripts/validation/validate_reference.py <file> --import`.
2. A working PHASE 0 environment on the RTX 5070 machine. The baseline tests in 1.4
   cannot run without ComfyUI and the Klein 4B models.

### Phase 2 — Prompt & Character Consistency

| Step | Deliverable | Status |
|------|-------------|--------|
| 2.1 Master prompt    | `prompts/master/master-character-v1.0.md` | Structure complete — slots filled from the bible |
| 2.2 Prompt variables | `prompts/README.md`, `scripts/generation/compile_prompt.py` | Complete |
| 2.3 Versioning       | filename + header versioning, enforced by `--lint` | Complete |
| 2.4 Deterministic seeds | seed = range base + canonical index | Complete |
| 2.5 Reference-edit tests | `tests/assets/phase2-reference-edit.md`, `prompts/diagnostic/` | Prompts written — **blocked on the PHASE 0 and PHASE 1 gates** |

The same two inputs unblock Phase 2. Nothing in Phase 2 has been validated against a
real generation.

### Phase 3 — Expression System

| Step | Deliverable | Status |
|------|-------------|--------|
| 3.1 Canonical set | 12 names, in `scripts/lib/canon.py` | Complete |
| 3.2 Dedicated prompts | `prompts/expressions/<name>-v1.0.md` × 12 | Complete |
| 3.3 Generation | `docs/workflows/expression-generation.md` | Runbook written — **blocked, not run** |
| 3.4 QC | `scripts/validation/validate_asset.py`, `scripts/utilities/contact_sheet.py` | Complete |
| 3.5 Lock | `validate_asset.py --set expression` | Tooling complete — 0/12 assets exist |

No expression asset has been generated. `character/expressions/` is empty.

### Phase 4 — Thai Viseme System

| Step | Deliverable | Status |
|------|-------------|--------|
| 4.1 Canonical set | 16 names, in `scripts/lib/canon.py` | Complete |
| 4.2 Thai mapping | `docs/thai-viseme/thai-viseme-mapping.md` | Complete — **unreviewed by a Thai speaker** |
| 4.3 Mouth anchor | `scripts/utilities/measure_anchor.py` | Tooling complete — **anchor unmeasured, needs the reference image** |
| 4.4 Generation | `prompts/visemes/` × 16, `docs/workflows/viseme-generation.md` | Prompts complete; runbook **blocked, not run** |
| 4.5 QC | containment check in `validate_asset.py` | Complete — reports SKIP until the anchor is measured |
| 4.6 Lock | `validate_asset.py --set viseme` | Tooling complete — 0/16 assets exist |

No viseme asset has been generated. `character/visemes/` is empty.
The Thai mapping needs review by a Thai speaker before PHASE 8 relies on it; `TH` has no
native Thai phoneme and is expected to be idle in most sentences.

### Phase 5 — Pose & Narrator Asset Library

| Step | Deliverable | Status |
|------|-------------|--------|
| 5.1 Pose set | `prompts/poses/<name>-v1.0.md` × 10 | Complete |
| 5.2 Camera set | `visual-spec.md` §2, `docs/workflows/pose-generation.md` | Complete — head heights are **ratios**; absolutes need the reference |
| 5.3 Compositions | `character/compositions/narrator-states.json` + validator | Complete |

No pose asset has been generated. `character/poses/` is empty.
PLAN §5 defines no QC or lock milestone; those requirements come from ASSET_SPEC §8 and
§10, and are covered by `validate_asset.py --set pose`.

### Phase 6 — Asset Validation & Production Lock

| Step | Deliverable | Status |
|------|-------------|--------|
| 6.1 Completeness | `scripts/validation/lock_library.py` gate, `validate_asset.py --approve` | Complete — **0/38 assets, gate fails on everything** |
| 6.2 Contact sheet | `contact_sheet.py --all` → three sheets at the paths the gate checks | Complete |
| 6.3 Resolution lock | 1024 enforced twice (header + recorded resolution); upscale derivative rule | Complete (ADR-017) |
| 6.4 Metadata lock | `metadata/production-lock.json`, `metadata/generations/` mirror, `--verify` | Complete (ADR-016) |
| 6.5 Production baseline | `docs/production-baseline.md`, generated from the lock | Complete — currently **NOT LOCKED** |
| Runbook | `docs/workflows/production-lock.md` | Written — **not run** |

The gate is the only thing that opens PHASE 7. Current output: 8 blocking problems — no
reference, no measured anchor, three empty sets, three missing sheets.

Two checks were wrong before PHASE 6 and are fixed:
- every pose is `medium` or wider, so head drift against the close-up reference would have
  failed all 10; it is now measured within a camera class (ADR-018)
- a per-asset `mouth_anchor` is only required once the PHASE 4.3 baseline is measured

### Phase 7 — Thai Audio / Phoneme Pipeline

Built ahead of the PHASE 6 gate on explicit instruction. The gate was **not** modified and
still fails on 8 problems (ADR-023).

| Step | Deliverable | Status |
|------|-------------|--------|
| 7.1 TTS | `scripts/audio/tts.py`, adapters `say` + `silence` | Complete — `say`/Kanya verified byte-deterministic; **production engine not selected** |
| 7.2 Phoneme analysis | `scripts/lib/thai_g2p.py`, `docs/audio/thai-lexicon.json` | Complete — rule parser + 20-entry lexicon; pythainlp is the recommended external engine, not installed |
| 7.3 Phoneme → viseme | `scripts/lib/viseme_map.py`, `docs/thai-viseme/thai-viseme-map.json` | Complete — JSON checked against the 4.2 markdown by test (ADR-019) |
| 7.4 Timeline | `scripts/lib/timeline.py`, `scripts/audio/build_timeline.py` | Complete — `timeline.json` per PLAN 7.4, plus provenance and digest (ADR-022) |
| QC | `scripts/validation/validate_timeline.py` | Complete — 15 negative tests |
| Runbook | `docs/audio/phase-7-audio-pipeline.md` | Written — quick start verified end to end |

78 tests, all passing; 279 across the repository. Verified end to end on real Thai audio:
text → `say` (Kanya) → 4.374s WAV → 29-event timeline → validator PASS.

What is **not** validated:
- no timing or shape has been seen against a real viseme image — 0/38 assets exist
- the Thai mapping is still unreviewed by a Thai speaker (PHASE 4.2)
- the duration model has never been checked against a measured alignment
- nothing emits `timing_source: aligned`; the best available is `fitted`

### Phase 8 — Lip-Sync Animation Engine

Built ahead of the PHASE 6 gate, on top of PHASE 7 which was also built ahead of it. The
gate was **not** modified and still fails on 8 problems (ADR-027).

| Step | Deliverable | Status |
|------|-------------|--------|
| 8.1 Mouth switching | `scripts/lib/animation.py` | Complete — flicker rule restated in frames, `min_frames_on_screen: 2` (ADR-026) |
| 8.2 Coarticulation | `docs/animation/coarticulation-model.json` | Complete — unreleased finals, closure protection, anticipatory rounding (ADR-025) |
| 8.3 Expression layer | `animation.py` expression track | Complete — open-mouth expressions refused under a viseme track (ADR-012) |
| 8.4 Secondary | `docs/animation/secondary-animation.json` | Complete — tracks not asset swaps; **blink cannot render, no eye region in ASSET_SPEC** |
| Compositing | `scripts/lib/compositor.py` | Complete — refuses without a measured anchor (PHASE 4.3) |
| Plan / render split | `build_animation.py`, `render_frames.py` | Complete (ADR-024) |
| QC | `scripts/validation/validate_animation.py` | Complete — 23 checks, 23 negative tests |
| Runbook | `docs/animation/phase-8-lipsync-engine.md` | Written — quick start verified end to end |

92 tests, all passing; 371 across the repository. Verified end to end against a
**synthetic** asset library: Thai text → timeline → frame plan → 66 rendered 1024x1024
RGBA PNGs → validator PASS.

What is **not** validated — and this differs from PHASE 7, which was fully testable:
- no real viseme has been composited onto a real expression; there are no assets
- whether a blend of two real mouths reads as a mouth moving is unknown
- `blend_ms`, the anticipatory window, and `min_frames_on_screen` are estimates until
  someone watches a pass
- blink timings are emitted but cannot be rendered — ASSET_SPEC defines a mouth anchor
  and no eye region (ADR-026)
- the Thai mapping is still unreviewed by a Thai speaker, now two phases deep

A guard test asserts `character/bible/mouth-anchor.json` is still unmeasured. When it
fails, PHASE 4.3 has happened and rendering is live.

## Decision Log

Add dated decisions here.

Format:

### YYYY-MM-DD — Decision
Context:
Decision:
Reason:
Impact:

### 2026-08-25 — Reference filename, diagnostic seeds
Context: PHASE 1 implementation surfaced two unspecified details.
Decision: Reference is `narra-reference-master-v1.png` with a byte-identical `master.png`
alias (ADR-008). Diagnostic and gate-test generations use seeds 1000–1999 (ADR-009).
Reason: Version history on the reference without rewriting workflow JSON on every bump;
diagnostic runs must not share seed space with library assets.
Impact: Enforced by `scripts/validation/validate_reference.py --check-imported`.

### 2026-08-25 — Preservation and negatives are generated
Context: The fixed PRESERVATION template and negative groups contradict themselves when
the TASK targets a feature they name.
Decision: Prompts declare `touches`; the compiler builds the preserved list and filters
negative terms from it (ADR-010).
Reason: A self-contradicting prompt produces unstable output that gets blamed on the model.
Impact: `PROMPT_GUIDE.md` §3 and §8 rewritten. Enforced by `compile_prompt.py --lint`.

### 2026-08-25 — Expressions do not move the head
Context: ASSET_SPEC §6 described `confused` with a head tilt and `proud` with a lifted chin.
Decision: Expression assets hold head angle, chin, and (for 9 of 12) the mouth fixed (ADR-012).
Reason: Moving the head moves the mouth anchor, so any viseme composited onto that asset
lands in the wrong place and the asset fails the §9 tolerance.
Impact: ASSET_SPEC §6 amended. `confused` is now carried by brow asymmetry alone.

### 2026-08-25 — Shared helper modules
Context: A second validator needed the image checks and canonical sets already written.
Decision: `scripts/lib/canon.py` and `scripts/lib/imagecheck.py`, imported via an explicit
sys.path insert; `validate_reference.py` and `compile_prompt.py` migrated onto them (ADR-011).
Reason: Two copies of the canonical viseme set would let QC approve an asset the compiler
could never have produced.
Impact: No new dependency and no package manifest; ADR-007 still holds.

### 2026-08-25 — Edit containment is measured, not eyeballed
Context: "Change only the mouth" was only checkable by eye through PHASE 3.
Decision: Record a permitted `edit_region` with the anchor; diff each viseme against the
reference and fail it if any changed pixel escapes that box (ADR-013).
Reason: The changed-pixel bounding box is direct evidence of what an edit touched; prompt
wording and denoise strength are only proxies for it.
Impact: Inert until the anchor is measured (PHASE 4.3, needs the reference image).

### 2026-08-25 — Camera classes are ratios, compositions are data
Context: PHASE 5 needed camera classes defined before the reference exists, and five
reusable narrator states.
Decision: Classes are specified as a ratio to the close-up head height (ADR-014). States
live in `character/compositions/narrator-states.json` and are validated (ADR-015).
Reason: The ratio is the decision, the absolute is a measurement. And an open-mouth
expression cannot host a viseme track — it would render two mouths.
Impact: The `explaining` state uses the `friendly` expression, not the `explaining` one.

## Full Decision Records

Dated architectural decisions with rationale and rejected alternatives live in `DECISIONS.md`.
This file keeps the short-form status; `DECISIONS.md` keeps the reasoning.

### 2026-08-25 — PHASE 6 gate reads recorded sign-offs
Context: PHASE 6 asks whether 38 assets are complete, correct, reviewed, and reproducible.
Through PHASE 5 only the machine half was checkable, and only one asset at a time.
Decision: `lock_library.py` runs the whole gate and writes `metadata/production-lock.json`;
`validate_asset.py --approve` records the human half; the baseline doc is generated from
the lock (ADR-016). Upscales are derivatives outside `character/` (ADR-017).
Reason: an unrecorded review is indistinguishable from no review, and a hand-written
baseline is stale from the first regeneration.
Impact: PHASE 7 is unblocked by `lock_library.py` exiting 0 and by nothing else.

### 2026-08-25 — Pose framing is checked within its camera class
Context: `validate_asset.py` measured head drift against the close-up reference. Every
pose in the library is `medium` or wider, so all 10 would have failed the PHASE 6 gate.
Decision: reference drift applies to close-up assets; poses are compared crown-to-crown
within their camera class against the same 1% tolerance (ADR-018).
Reason: ASSET_SPEC §2 and §8 already define pose consistency as within-class. Comparing a
three-quarter shot to a close-up measures the camera move, not a defect.
Impact: head *height* per class stays a human check — alpha cannot separate head from body.

### 2026-08-27 — PHASE 7 built ahead of the image gate
Context: PLAN, CLAUDE.md, and README all gate PHASE 7 behind a passing PHASE 6.
`lock_library.py` fails on 8 problems and 0/38 assets exist.
Decision: PHASE 7 implemented on the owner's explicit, repeated instruction after the
conflict was raised and overruled. The gate was not modified (ADR-023).
Reason: the owner's instruction outranks the plan the owner wrote; an override recorded
with its cost keeps the gate meaningful, a bypassed one does not.
Impact: PHASE 8 stays blocked. Every timeline carries `timing_source` and the unreviewed-
mapping warning, so nothing downstream can mistake an estimate for a measurement.

### 2026-08-27 — Thai G2P is rules plus a lexicon, not a dictionary
Context: Thai spelling underdetermines pronunciation; ดีครับ is /diː.kʰrap/ and no rule
says so.
Decision: score whole segmentations rather than matching greedily, and override the
remainder from `docs/audio/thai-lexicon.json` (ADR-020).
Reason: rule patches interact unboundedly and their damage is invisible; a lexicon entry
is scoped to one word and is data, not code.
Impact: `build_timeline.py --report` is the way to find lexicon candidates. Coverage is
recorded per timeline and a build below 95% exits non-zero.

### 2026-08-27 — PHASE 8 built ahead of the gate, on synthetic assets
Context: PHASE 8 requested after the gate objection was raised and overruled a second
time (ADR-027). Unlike PHASE 7, PHASE 8's whole job is compositing images that do not
exist.
Decision: implemented, tested against synthetic PNGs generated in a temp directory. The
gate was not modified.
Reason: the compositing contract — the mouth region changes and nothing else — is
testable without the real library, and untested code would be worse than either.
Impact: verifies the contract, verifies nothing about the character. Two phases of tuned
constants now rest on assumptions one rendered frame could invalidate.

### 2026-08-27 — ASSET_SPEC defines no eye region
Context: PLAN 8.4 asks for blinking. ASSET_SPEC §9 defines a mouth anchor and mouth
edit region — nothing has needed an eye region until now.
Decision: emit blink timings anyway, record the gap in `secondary-animation.json` and the
runbook, do not invent a region (ADR-026).
Reason: the timing is a real animation decision worth having; guessing where the eyes are
is not.
Impact: blink cannot be rendered. Closing the gap means measuring an eye region the way
§9 measures the mouth, or adding eye-state assets — an asset-spec or PHASE 9 decision.
