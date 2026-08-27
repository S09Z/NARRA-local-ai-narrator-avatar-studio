# PHASE 2.5 — Reference-Edit Containment Tests

Status: **NOT RUN** — blocked on the PHASE 0 gate and the PHASE 1 gate
Prompts: `prompts/diagnostic/change-only-*-v1.0.md`
Acceptance (`PLAN.md` §2.5): *"unrequested properties remain stable."*

---

## 1. What this proves

PHASE 1.4 asked whether the character survives being regenerated. PHASE 2.5 asks a
different and sharper question: **when the prompt names one region, does exactly one
region change?**

That property is what the entire asset library rests on. `DECISIONS.md` → ADR-003 makes
reference editing the default generation method, and ADR-004 splits expression and viseme
into independent layers — both assume a named edit stays inside its boundary. If it does
not, 12 expressions and 16 visemes will each drag a slightly different face along with
them and nothing will composite.

| Test | Prompt | Seed | Touches | Previews |
|------|--------|------|---------|----------|
| E1 | `change-only-hair-v1.0.md` | 1011 | `hair` | nothing — pure containment probe |
| E2 | `change-only-eyes-v1.0.md` | 1012 | `eyes` | the hardest region to isolate |
| E3 | `change-only-mouth-v1.0.md` | 1013 | `mouth` | PHASE 4 (visemes) |
| E4 | `change-only-expression-v1.0.md` | 1014 | `eyes, eyebrows, mouth` | PHASE 3 (expressions) |

E1 and E2 deliberately request changes the library will never actually want. The point is
not the new hair or the new eye color — it is everything that was *not* asked for.

Seeds are in the diagnostic range (`DECISIONS.md` → ADR-009). Outputs are never promoted
to `character/`.

---

## 2. Prerequisites

- [ ] PHASE 0 gate passed — ComfyUI launches, Klein 4B loads, test image succeeds
- [ ] PHASE 1 gate passed — `tests/assets/phase1-baseline.md` B1–B3 all pass
- [ ] Reference imported: `python3 scripts/validation/validate_reference.py --check-imported` exits 0
- [ ] `character/bible/character-bible.md` filled — no `TBD` in §1–§11
- [ ] `prompts/master/master-character-v1.0.md` filled from the bible — no `<...>` slots left
- [ ] `python3 scripts/generation/compile_prompt.py --lint` exits 0

The PHASE 1 gate genuinely blocks this one. Containment is only meaningful against a
reference that reproduces stably; testing containment on an unstable reference measures
two failures at once and attributes them to the wrong cause.

---

## 3. Fixed conditions

| Setting     | Value                                     | Source                 |
|-------------|-------------------------------------------|------------------------|
| Model       | FLUX.2 Klein 4B **Base**                  | `DECISIONS.md` ADR-002 |
| Method      | reference edit from `master.png`           | `DECISIONS.md` ADR-003 |
| Resolution  | 1024 x 1024                                | `ASSET_SPEC.md` §1     |
| Batch size  | 1                                          | `CLAUDE.md`            |
| Seed        | from the prompt file, unchanged on reruns  | `DECISIONS.md` ADR-009 |
| Denoise     | as low as the change allows                | `PROMPT_GUIDE.md` §4   |

Compile each prompt rather than retyping it, so the text under test is the text the
library will actually use:

```bash
python3 scripts/generation/compile_prompt.py diagnostic/change-only-hair-v1.0.md
python3 scripts/generation/compile_prompt.py diagnostic/change-only-hair-v1.0.md --json \
  > metadata/prompts/change-only-hair-v1.0.json
```

---

## 4. Acceptance criteria

Per output. The *requested* change is not scored — only containment.

**E1 — change only hair**
- [ ] Hair changed as asked
- [ ] Face proportions, head shape unchanged
- [ ] Eyes, eyebrows, nose unchanged
- [ ] Mouth shape and position unchanged
- [ ] Skin tone unchanged
- [ ] Clothing and accessories unchanged
- [ ] Art style, line style, lighting direction unchanged
- [ ] Head size and position within tolerance (`visual-spec.md` §4)

**E2 — change only eyes**
- [ ] Iris color changed as asked
- [ ] Eye *shape*, *size*, and *position* unchanged — only color moved
- [ ] Eyebrows unchanged
- [ ] Everything in the E1 list except eyes unchanged

**E3 — change only mouth**
- [ ] Mouth shape changed as asked
- [ ] Mouth anchor within 0.5% of image width (`ASSET_SPEC.md` §9)
- [ ] Eyes, eyebrows, gaze, head angle unchanged
- [ ] Everything in the E1 list except mouth unchanged

**E4 — change only expression**
- [ ] Expression reads as concerned at 256px
- [ ] Hair, skin, clothing, accessories, style, lighting unchanged
- [ ] Head size and position within tolerance
- [ ] Nose and face proportions unchanged

Any unrequested change is a FAILED result. "It still looks like the same person" is not
the criterion — `PLAN.md` §2.5 says *unrequested properties remain stable*, which is a
stricter test and the one that matters for compositing.

---

## 5. Interpreting failures

| Symptom | Reading | Action |
|---------|---------|--------|
| Whole face resampled on every test | Edit is not localized | Fix the workflow's region constraint, not the prompt (`PROMPT_GUIDE.md` §4) |
| Only E2 leaks into the face | Eyes are entangled with identity | Lower denoise; tighten the edit region |
| Only E3 leaks into eyes/brows | Mouth edit region is too large | Shrink the region; this is a direct PHASE 4 blocker |
| E4 leaks but E2/E3 hold | Three regions at once is too much | Split into staged edits; record in `character-bible.md` §15 |
| Drift needs a high denoise to show the change | The prompt is wrong, not the strength | Rewrite the descriptor (`PROMPT_GUIDE.md` §4) |

Every drift observed here goes into `character-bible.md` §15 with the fix, and only then
may a matching negative term be added (`PROMPT_GUIDE.md` §8). That ordering is what keeps
the negative prompt short and meaningful instead of accumulating superstition.

---

## 6. Results

Outputs to `assets/generated/phase2-reference-edit/` — diagnostics, not committed
(`DECISIONS.md` → ADR-006). QC outcome to `metadata/validation/phase2-reference-edit.json`.

| Test | Seed | Denoise | Requested change | Containment | Notes |
|------|------|---------|------------------|-------------|-------|
| E1 hair       | 1011 | — | NOT RUN | NOT RUN | — |
| E2 eyes       | 1012 | — | NOT RUN | NOT RUN | — |
| E3 mouth      | 1013 | — | NOT RUN | NOT RUN | — |
| E4 expression | 1014 | — | NOT RUN | NOT RUN | — |

Contact sheet: `assets/contact-sheets/narra-sheet-phase2-reference-edit-v1.png` — the
reference and all four outputs at 256px. Containment failures that are arguable at full
size are obvious in a row of thumbnails.

**Gate on PHASE 3:** E3 and E4 are the direct precursors of the viseme and expression
sets. Do not start PHASE 3 while either is failing containment — the failure will simply
be reproduced 12 or 16 times.
