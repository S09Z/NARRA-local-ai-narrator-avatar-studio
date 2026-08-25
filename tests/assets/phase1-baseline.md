# PHASE 1.4 — Baseline Identity Tests

Status: **NOT RUN** — blocked on the PHASE 0 gate
Reference under test: `character/reference/narra-reference-master-v1.png`
Gate: `PLAN.md` → PHASE 1 GATE — "Do not continue if identity is unstable."

---

## 1. What this proves

Three generations, deliberately chosen to be the easiest possible edits:

| Test | Asset            | Edit region              | Proves                                       |
|------|------------------|--------------------------|-----------------------------------------------|
| B1   | `neutral`        | none (round-trip)        | the pipeline can reproduce the reference       |
| B2   | `slight-smile`   | mouth corners + cheeks   | a small edit does not disturb identity         |
| B3   | `speaking`       | mouth open, jaw dropped  | an open mouth does not disturb identity        |

If identity survives these three, the reference is a workable source of truth and PHASE 2
can proceed. If it does not, no amount of prompt engineering in later phases will fix it —
the reference itself is replaced.

This is not an expression set. PHASE 3 generates the 12 canonical expressions. B2 and B3
are diagnostics and are **not** stored in `character/expressions/`.

---

## 2. Prerequisites

Run only when all of these hold:

- [ ] PHASE 0 gate passed: ComfyUI launches, Klein 4B loads, a test image succeeds,
      VRAM usage is practical (`PLAN.md` → PHASE 0.1)
- [ ] Both models present: FLUX.2 Klein 4B Distilled and Base (`PLAN.md` → PHASE 0.2)
- [ ] `workflows/reference-edit/` contains a working reference-edit workflow
      (`PLAN.md` → PHASE 0.3)
- [ ] Reference imported and verified:
      `python3 scripts/validation/validate_reference.py --check-imported` exits 0
- [ ] `character/bible/character-bible.md` filled from the reference — no `TBD` in §1–§11
- [ ] `character/bible/visual-spec.md` §3 landmarks measured

The bible must be filled first: the prompts below embed the CHARACTER block, and an
unfilled block means FLUX invents the parts that were left out.

---

## 3. Fixed conditions

Held identical across all three tests, so any difference in output is attributable to
the prompt and not to the settings.

| Setting     | Value                                   | Source              |
|-------------|-----------------------------------------|---------------------|
| Model       | FLUX.2 Klein 4B **Base**                | `DECISIONS.md` ADR-002 |
| Method      | reference edit from `master.png`         | `DECISIONS.md` ADR-003 |
| Resolution  | 1024 x 1024                              | `ASSET_SPEC.md` §1  |
| Batch size  | 1                                        | `CLAUDE.md`         |
| Precision   | FP8                                      | `CLAUDE.md`         |
| Seed        | fixed per test (§4), reused on every rerun | `DECISIONS.md` ADR-009 |

Baseline seed range: **1000–1999** (`DECISIONS.md` → ADR-009). Distinct from the
expression / viseme / pose ranges so diagnostic runs never collide with library assets.

Every derived asset edits `master.png`, never another derived asset — editing a derived
asset compounds drift (`PROMPT_GUIDE.md` §4).

---

## 4. The tests

Prompts follow `PROMPT_GUIDE.md` §1 block order. `<MASTER>` is the CHARACTER + STYLE +
LIGHTING + CAMERA text from `prompts/master/master-character-v1.0.md`; in PHASE 1 that
file does not exist yet, so paste the equivalent content from
`character/bible/character-bible.md` and record what was used.

### B1 — neutral round-trip

Seed: `1001` · Denoise: lowest the workflow allows while still resampling

```
<MASTER>

PRESERVATION:
  Keep the same person: identical face shape, eye shape and position, eyebrows,
  nose, hairstyle, hair color, skin tone, clothing, accessories, art style,
  lighting, and camera framing as the reference image.
  Do not change anything.

TASK:
  Reproduce the reference image exactly.

OUTPUT:
  1024x1024, square, flat uniform background.

NEGATIVE:
  different person, different face shape, different hairstyle, different hair color,
  different clothing, aged face, changed camera distance, changed head size
```

Expected: visually indistinguishable from the reference. This is the control — a
failure here means the pipeline itself is lossy and B2/B3 results carry no information.

### B2 — slight smile

Seed: `1002` · Denoise: as low as the change allows

```
<MASTER>

PRESERVATION:
  Keep the same person: identical face shape, eye shape and position, eyebrows,
  nose, hairstyle, hair color, skin tone, clothing, accessories, art style,
  lighting, and camera framing as the reference image.
  Do not change anything except the mouth corners and cheeks.

TASK:
  Change only the mouth corners and cheeks. Everything else is identical.

EXPRESSION:
  Mouth corners lifted slightly, lips still together. Cheeks raised a little.
  Eyes unchanged, eyebrows unchanged, gaze at camera. Intensity: subtle.

OUTPUT:
  1024x1024, square, flat uniform background.

NEGATIVE:
  different person, different face shape, different hairstyle, changed eyes,
  changed eyebrows, changed head size, teeth visible
```

Expected: a readable but subtle smile. Eyes, brows, hair, clothing pixel-stable.

### B3 — speaking

Seed: `1003` · Denoise: as low as the change allows

```
<MASTER>

PRESERVATION:
  Keep the same person: identical face shape, eye shape and position, eyebrows,
  nose, hairstyle, hair color, skin tone, clothing, accessories, art style,
  lighting, and camera framing as the reference image.
  Do not change anything except the mouth and jaw.

TASK:
  Change only the mouth and jaw. Everything else is identical.

VISEME SPEAKING:
  jaw: open
  lips: neutral width, relaxed
  opening: moderate, mid-speech
  width: neutral
  teeth: upper visible
  tongue: hidden

OUTPUT:
  1024x1024, square, flat uniform background.

NEGATIVE:
  different person, changed eyes, changed eyebrows, changed expression,
  moved mouth position, changed head size, changed camera distance
```

Expected: an open mouth with everything above the upper lip unchanged. This is the
hardest of the three and the closest preview of PHASE 4.

---

## 5. Acceptance criteria

`PLAN.md` PHASE 1.4: *"character remains recognizable and visually consistent."* Made
checkable, per output:

**Identity** (`ASSET_SPEC.md` §10)
- [ ] Same person — face proportions and head shape unchanged
- [ ] Eye shape, eye color, eye position unchanged
- [ ] Eyebrow shape and thickness unchanged
- [ ] Hairstyle, hair color, hair part unchanged
- [ ] Skin tone unchanged
- [ ] Clothing and accessories unchanged

**Render**
- [ ] Art style and line style consistent with the reference
- [ ] Lighting direction unchanged — the shadow side did not flip
- [ ] No photorealistic drift, no added text, no artifacts

**Framing** (`visual-spec.md` §3–4)
- [ ] Head vertical drift ≤ 1% of image height (≤ 10 px at 1024)
- [ ] Mouth anchor drift ≤ 0.5% of image width (≤ 5 px at 1024)
- [ ] Head size in frame matches the reference

**Task containment**
- [ ] B1: nothing changed
- [ ] B2: only mouth corners and cheeks changed
- [ ] B3: only mouth and jaw changed

Anything that changed outside the task target is a FAILED result, regardless of how good
the image looks (`PROMPT_GUIDE.md` §3).

---

## 6. Gate decision

| Outcome                        | Decision                                             |
|--------------------------------|------------------------------------------------------|
| B1, B2, B3 all pass            | PHASE 1 GATE PASSED → proceed to PHASE 2             |
| B1 fails                       | Pipeline problem, not a prompt problem. Fix the workflow or denoise before re-testing. |
| B1 passes, B2 or B3 fails on identity | Strengthen PRESERVATION and retry once. Second failure → the reference is unsuitable; replace it and restart PHASE 1. |
| B2 or B3 fails on containment only | Tighten the edit region in the workflow and retry.  |

Two failed attempts on the same test with the same reference means the reference is
replaced, not the prompt rewritten again. Discovering this now is the entire point of
having a PHASE 1 gate (`DECISIONS.md` → ADR-001).

---

## 7. Results

Fill on execution. Store outputs in `assets/generated/phase1-baseline/` — they are
diagnostics and are not committed (`DECISIONS.md` → ADR-006). Record the QC outcome in
`metadata/validation/phase1-baseline.json`.

| Test | Seed | Model | Denoise | Result | Notes |
|------|------|-------|---------|--------|-------|
| B1 neutral      | 1001 | — | — | NOT RUN | — |
| B2 slight-smile | 1002 | — | — | NOT RUN | — |
| B3 speaking     | 1003 | — | — | NOT RUN | — |

Contact sheet for side-by-side review: `assets/contact-sheets/narra-sheet-phase1-baseline-v1.png`
— reference and all three outputs at 256px, which is the size at which subtle identity
drift stops being deniable.

Any drift observed here is recorded in `character-bible.md` §15 with the prompt change
that fixed it, so PHASE 3 and PHASE 4 inherit the fix instead of rediscovering it.
