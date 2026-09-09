# GUIDELINE.md

# NARRA — Step-by-Step Operating Guide

The ordered procedure for taking this repository from a fresh checkout to a locked
avatar library and, after that, to rendered lip-sync frames.

It is deliberately narrow. Other documents answer other questions:

| Question | Document |
|----------|----------|
| What are the phases and why | `PLAN.md` |
| What must an asset satisfy | `ASSET_SPEC.md` |
| Why the architecture is like this | `DECISIONS.md` |
| How to write a prompt | `PROMPT_GUIDE.md` |
| Deep runbook for one phase | `docs/workflows/`, `docs/operations/` |
| Where the project is right now | `make status` |
| **What do I do next, in what order** | **this file** |

Two machines are involved. Most steps run anywhere; generation runs only on the
RTX 5070 box. Each step below says which.

---

## 0. Demo first run

Start here, on any machine, before installing anything heavy.

```bash
make demo
```

It walks all eight checkpoints in order, prints the real command for each one, runs
it, and reports the result. **It generates nothing, writes nothing, and installs
nothing** — it is safe against a live library and safe on a laptop with no GPU.

Every step reports one of three outcomes:

| Outcome   | Meaning                                                            |
|-----------|--------------------------------------------------------------------|
| `OK`      | the check passes today                                             |
| `TODO`    | work waiting for a person, doable on this machine                  |
| `BLOCKED` | waiting on something this machine does not have (PHASE 0, the GPU) |

The last two lines are the point of the exercise:

```
Summary
  OK 3   TODO 3   BLOCKED 2

Next
  step 3 (bible) - 290 fields still TBD
```

Options:

```bash
make demo                                        # the whole walkthrough
python3 scripts/utilities/demo_run.py --list     # the steps, without running them
python3 scripts/utilities/demo_run.py --step anchor   # one step (repeatable)
python3 scripts/utilities/demo_run.py --verbose  # full output of every command
python3 scripts/utilities/demo_run.py --json     # the same results, machine-readable
make demo ARGS="--step gate --verbose"           # the same, through make
```

The walkthrough always exits 0, even on a project in poor shape. It reports; it does
not judge. `make gate` is the thing that judges.

`make demo` maps onto steps 1, 3, 4, 5, 7, 8–10, and 11–12 below. It cannot run the
generation steps, and says so rather than pretending.

---

## Map

| # | Step | Phase | Machine | Blocks |
|---|------|-------|---------|--------|
| 1 | Toolchain | 0.1 | any | everything |
| 2 | ComfyUI, models, workflows | 0.1–0.3 | **GPU** | all generation |
| 3 | Import the reference | 1.1 | any | all derived assets |
| 4 | Fill the character bible | 1.2–1.3 | any | every prompt |
| 5 | Measure the mouth anchor | 4.3 | any | visemes, PHASE 6 gate |
| 6 | Baseline identity tests | 1.4 | **GPU** | PHASE 2 onward |
| 7 | Prompt system | 2 | any | generation |
| 8 | Expressions ×12 | 3 | **GPU** | PHASE 6 |
| 9 | Visemes ×16 | 4 | **GPU** | PHASE 6 |
| 10 | Poses ×10 + compositions | 5 | **GPU** | PHASE 6 |
| 11 | QC and contact sheets | 6.1–6.2 | any | the lock |
| 12 | Production lock | 6.3–6.5 | any | PHASE 7–10 |
| 13 | Thai audio and timelines | 7 | any | PHASE 8 |
| 14 | Lip-sync frames | 8 | any | PHASE 9 |
| 15 | Video plan and MP4 | 9 | any | PHASE 10 |

Steps 1, 3, 4, 5, 7 are doable today on a laptop. Nothing between step 6 and step 10
is.

---

## Step 1 — Toolchain

**Where:** any machine. **Phase:** 0.1.

Python ≥ 3.10 and Pillow. Without Pillow every pixel check reports `SKIP` rather than
`PASS` (`scripts/lib/imagecheck.py`) — a missing dependency must never look like a
pass.

```bash
make install     # poetry install into .venv
make check       # test suite + prompt lint
make demo ARGS="--step toolchain"
```

**Pass when:** `make check` is green and step 1 of the demo reports `OK`.

A system `python3` older than 3.10 works for most scripts but is not the supported
interpreter. Use `.venv/bin/python`, or pass `PYTHON=` to make.

---

## Step 2 — ComfyUI, models, workflows

**Where:** the RTX 5070 machine only. **Phase:** 0.1–0.3.
**Runbook:** `docs/operations/phase-0-environment-setup.md`.

Install ComfyUI + ComfyUI Manager, place FLUX.2 Klein 4B **Distilled** (default) and
**Base** (quality/editing), and build the reference-edit workflow under
`workflows/reference-edit/`.

Constraints that are not negotiable here (`CLAUDE.md`): 12 GB VRAM target, batch size
1, 1024×1024, FP8 where appropriate, no `--lowvram` by default, and no custom node
installed without a recorded reason and version.

**Pass when:** ComfyUI launches, Klein 4B loads, one test image generates, VRAM usage
is practical, and both models are present.

**Blocks:** steps 6, 8, 9, 10. Until this is done, `MEMORY.md` should keep saying so.

---

## Step 3 — Import the reference

**Where:** any machine. **Phase:** 1.1. **Detail:** `character/reference/README.md`.

The canonical image is the source of truth for all 38 assets. Everything else in
`character/` is a reference edit of it (`DECISIONS.md` → ADR-003).

```bash
# 1. validate a candidate — writes nothing
python3 scripts/validation/validate_reference.py assets/input/candidate.png

# 2. optional: mechanically correct resolution / near-opaque alpha
python3 scripts/utilities/prep_reference.py assets/input/candidate.png

# 3. import — writes the versioned master, master.png, and the sidecar
python3 scripts/validation/validate_reference.py assets/input/candidate-prepped.png --import

# 4. re-verify what landed
python3 scripts/validation/validate_reference.py --check-imported
```

The automated checks cover resolution, aspect, bit depth, RGBA, colour space, and
alpha. **They cannot check the two things that matter most**, which the script prints
as an unticked list:

- **REST mouth** — relaxed and closed. All 16 visemes are edits of this mouth.
- **Head angle and size** — whichever they are, the whole library is stuck with them.

Confirm those by eye before continuing. Replacing the reference later invalidates
every derived asset, with no partial migration (`character/reference/README.md` §4).

**Pass when:** `--check-imported` exits 0 **and** the six visual checks are confirmed.

**Then:** commit the master, `master.png`, and both sidecars. Change control assumes
v1 is in git history before anything edits from it.

---

## Step 4 — Fill the character bible

**Where:** any machine. **Phase:** 1.2–1.3.

`character/bible/character-bible.md` and `character/bible/visual-spec.md` are not
documentation. They compile into the CHARACTER and PRESERVATION blocks of every
prompt (`PROMPT_GUIDE.md`). See it for yourself:

```bash
python3 scripts/generation/compile_prompt.py visemes/mbp-v1.0.md
```

Every `<...>` in that output is a field FLUX would otherwise invent — differently on
each generation, which is exactly how a character stops being consistent.

Fill each field from the imported reference image: face, eyes, eyebrows, hair, skin,
clothing, accessories, art style, lighting. Concrete visual nouns, not adjectives.

**Pass when:** no `TBD` remains, and a compiled prompt contains no `<...>` slots.
Confirm with `python3 scripts/utilities/demo_run.py --step bible --step compile`.

**Blocks:** step 6 lists this as a prerequisite (`tests/assets/phase1-baseline.md` §2).

---

## Step 5 — Measure the mouth anchor

**Where:** any machine. **Phase:** 4.3.

One measurement taken once from the approved reference, then enforced on every
derived asset within 0.5% of image width (`ASSET_SPEC.md` §9). It is what keeps
expression frames and viseme frames interchangeable in a composite.

```bash
# read the REST mouth bounding box off the reference in any image editor, then:
python3 scripts/utilities/measure_anchor.py --box LEFT TOP RIGHT BOTTOM
python3 scripts/utilities/measure_anchor.py --show
```

`--edit-region` is derived from `--box` unless given explicitly; it is the mask region
viseme edits are allowed to touch.

**Pass when:** `character/bible/mouth-anchor.json` has `"status": "measured"` and no
null in `anchor`.

**Blocks:** the PHASE 6 gate fails on `anchor/measured` until this exists, no matter
how many assets are generated.

---

## Step 6 — Baseline identity tests

**Where:** the RTX 5070 machine. **Phase:** 1.4.
**Procedure:** `tests/assets/phase1-baseline.md`.

Three deliberately easy generations, before spending 38 of them:

| Test | Edit | Proves |
|------|------|--------|
| B1 | none (round-trip) | the pipeline reproduces the reference |
| B2 | mouth corners + cheeks | a small edit does not disturb identity |
| B3 | mouth open, jaw dropped | an open mouth does not disturb identity |

Fixed conditions across all three — Klein 4B **Base**, reference edit from
`master.png`, 1024×1024, batch 1, FP8, fixed seed per test — so any difference is
attributable to the prompt and nothing else.

B2 and B3 are diagnostics. They are **not** stored in `character/expressions/`.

**PHASE 1 GATE:** if identity does not survive these three, no prompt engineering in
later phases will rescue it. Replace the reference and repeat from step 3.

---

## Step 7 — Prompt system

**Where:** any machine. **Phase:** 2.

The 38 prompt sources already exist under `prompts/`. What this step verifies is that
they are structurally sound and deterministically seeded before generation consumes
them.

```bash
make lint                                              # every prompt source
python3 scripts/generation/compile_prompt.py poses/explaining-v1.0.md
python3 scripts/generation/compile_prompt.py visemes/mbp-v1.0.md --json
```

Seeds are derived, not chosen: `canon.derive_seed()` (`scripts/lib/canon.py`) gives
each asset a fixed seed inside its type's band, so a rerun reproduces rather than
resamples.

**Pass when:** `make lint` exits 0 and compiled prompts carry no `<...>` slots.

---

## Steps 8–10 — Generate the library

**Where:** the RTX 5070 machine. **Phases:** 3, 4, 5.
**Runbooks:** `docs/workflows/expression-generation.md`,
`docs/workflows/viseme-generation.md`, `docs/workflows/pose-generation.md`.

| Step | Set | Count | Canonical names |
|------|-----|-------|-----------------|
| 8 | Expressions | 12 | neutral, friendly, happy, excited, serious, concerned, surprised, confused, thinking, explaining, proud, embarrassed |
| 9 | Visemes | 16 | REST, A, I, U, E, O, AE, AO, MBP, FV, TH, KG, S, SH, L, N |
| 10 | Poses | 10 | neutral, explaining, pointing-left, pointing-right, presenting, surprised, thinking, concerned, confident, excited |

The method is the same for all three, one asset at a time:

```bash
python3 scripts/generation/compile_prompt.py expressions/happy-v1.0.md   # 1. compile
# 2. reference-edit in ComfyUI from character/reference/master.png, fixed seed
python3 scripts/validation/validate_asset.py assets/generated/narra-expression-happy-v1.png
# 3. iterate until it passes, then place it in character/expressions/
```

Rules that decide whether an asset is acceptable:

- Edit the reference; do not regenerate the character (`DECISIONS.md` → ADR-003).
- Change only what the asset is named for. If an unrelated feature moved, it FAILED —
  regenerate with stronger preservation, do not accept and move on.
- Expression and viseme layers stay independent: same head size, same anchor, so they
  composite (`ASSET_SPEC.md` §9).
- `MBP` must be visually distinct from `REST` (`CLAUDE.md`). This is the single most
  common viseme failure.
- Poses may use a wider camera class, but each camera class is internally consistent.

Step 10 also fills `character/compositions/narrator-states.json`:

```bash
python3 scripts/validation/validate_compositions.py
```

**Pass when:** each set reports complete —
`python3 scripts/validation/validate_asset.py --set viseme`.

---

## Step 11 — QC and contact sheets

**Where:** any machine. **Phase:** 6.1–6.2.

Automated validation is necessary and not sufficient; all 38 assets need a recorded
human sign-off.

```bash
python3 scripts/validation/validate_asset.py <asset>.png --record
python3 scripts/validation/validate_asset.py <asset>.png --approve "Your Name" --notes "..."
python3 scripts/utilities/contact_sheet.py --all
```

`--approve` is refused if any automated check FAILs, so a sign-off can never
contradict the spec. Sheets land in `assets/contact-sheets/` and are what a person
actually reviews — drift is visible side by side and invisible one file at a time.

**Pass when:** 38 approved records under `metadata/validation/` and all three sheets
built.

---

## Step 12 — Production lock

**Where:** any machine. **Phase:** 6.3–6.5.
**Runbook:** `docs/workflows/production-lock.md`.

```bash
make gate                                    # reports only, writes nothing
python3 scripts/validation/lock_library.py --lock --by "Your Name"
python3 scripts/validation/lock_library.py --verify
python3 scripts/validation/lock_library.py --baseline
```

The gate checks completeness of all three sets, the measured anchor, resolution,
metadata, contact sheets, and that any upscale names the exact locked master it came
from (`ASSET_SPEC.md` §1).

**IMAGE PIPELINE GATE.** `CLAUDE.md` blocks PHASE 7–10 until this passes. Steps 13 and
14 have tooling and documentation already, but no locked assets to run against, and
nothing downstream should be treated as real until this step is green.

**Pass when:** `metadata/production-lock.json` is written and `--verify` exits 0.

---

## Step 13 — Thai audio and viseme timelines

**Where:** any machine. **Phase:** 7. **Runbook:** `docs/audio/phase-7-audio-pipeline.md`.

```bash
python3 scripts/audio/tts.py "สวัสดีครับ" --out assets/audio/greeting.wav
python3 scripts/audio/build_timeline.py --text-file script.txt --tts --name greeting
python3 scripts/validation/validate_timeline.py --all
```

Thai text → G2P → phonemes → the 16-viseme set → a timed timeline in
`metadata/timelines/`. The viseme set is a visual approximation for animation, not a
complete Thai phonological model.

**Pass when:** `validate_timeline.py --all` exits 0 and every viseme in the timeline
exists in the locked library.

---

## Step 14 — Lip-sync frames

**Where:** any machine. **Phase:** 8. **Runbook:** `docs/animation/phase-8-lipsync-engine.md`.

```bash
python3 scripts/animation/build_animation.py metadata/timelines/greeting.json --fps 30
python3 scripts/validation/validate_animation.py --all
python3 scripts/animation/render_frames.py metadata/animations/greeting.json --check
python3 scripts/animation/render_frames.py metadata/animations/greeting.json
```

The frame plan composites a pose, an expression, and a viseme per frame, with
coarticulation and secondary animation applied from
`docs/animation/coarticulation-model.json` and `secondary-animation.json`.

`--check` validates the plan without writing frames. Run it first.

**Pass when:** frames render, and `validate_animation.py --strict` exits 0.

---

## Step 15 — Video plan and MP4

**Where:** any machine. **Phase:** 9. **Runbook:** `docs/video/phase-9-video-pipeline.md`.

```bash
python3 scripts/video/build_video.py metadata/animations/greeting-animation-v1.json \
        --move slow-push
python3 scripts/validation/validate_video.py metadata/videos/greeting-video-v1.json
python3 scripts/video/render_video.py metadata/videos/greeting-video-v1.json --check
python3 scripts/video/render_video.py metadata/videos/greeting-video-v1.json
```

The frame plan carries the character; this step carries everything around it — canvas,
camera, Thai subtitles, b-roll, and the encode. As in PHASE 8, the plan is a separate
artefact from the render (ADR-032), because a cue that outruns its audio or a push-in
that has become an upscale is decidable before spending an encode.

Three things to know before using it:

- **Subtitles ship as a `.srt` sidecar, not burned in.** Pillow here cannot shape Thai,
  so burn-in goes through ffmpeg's libass and is opt-in (ADR-035). The sidecar is also
  what a Thai reviewer can correct.
- **The camera cannot invent detail.** `validate_video.py` warns when a push-in draws a
  source pixel larger than an output pixel. `--strict` makes that a failure.
- **HyperFrames and GSAP are declared, not wired up.** The plan carries GSAP easing
  names and the same curve sampled per frame; ffmpeg is the only implemented engine
  (ADR-032).

**Needs:** ffmpeg on PATH, plus the PHASE 8 frames — so, the image library.
`--check` reports which of those are missing without decoding anything.

**Pass when:** `validate_video.py --strict` exits 0 and `render_video.py --check`
reports ready.

---

## Rules that apply at every step

- **Inspect → understand → propose → implement → test → report.** Never reinstall,
  replace CUDA, install random nodes, overwrite workflows, or delete models.
- **Reproducibility.** Seed, model, prompt, workflow, reference, resolution, settings,
  and node versions are recorded per asset (`ASSET_SPEC.md` §11).
- **When a result is good, lock it.** Do not regenerate a successful asset without a
  reason.
- **Preservation is explicit.** Every edit prompt names what must not change.
- **A version bump on the reference is a full library regeneration**, recorded as an
  ADR in `DECISIONS.md`.
- **The gate is `make gate`.** `make demo` and `make status` report; only the gate
  decides.

---

## When something is wrong

| Symptom | Look at |
|---------|---------|
| Where am I? | `make status` |
| What do I do next? | `make demo` |
| Why does the gate fail? | `python3 scripts/validation/lock_library.py` |
| An asset changed the wrong feature | `PROMPT_GUIDE.md`, preservation block |
| Identity drifts across generations | step 6 — the reference itself may be at fault |
| VRAM, node, or model failure | `TROUBLESHOOTING.md` |
| Why is it built this way | `DECISIONS.md` |
| A subtitle reads wrong in Thai | `docs/video/phase-9-video-pipeline.md` §3 |
