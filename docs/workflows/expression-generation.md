# Expression Generation Runbook — PHASE 3.3 / 3.5

Status: **NOT RUN** — blocked on the PHASE 0, PHASE 1, and PHASE 2.5 gates
Prompts: `prompts/expressions/<name>-v1.0.md` — 12 files, complete
Output: `character/expressions/` on approval

---

## 1. Before starting

- [ ] PHASE 0 gate — ComfyUI launches, Klein 4B loads, test image succeeds
- [ ] PHASE 1 gate — `tests/assets/phase1-baseline.md` B1–B3 pass
- [ ] PHASE 2.5 — `tests/assets/phase2-reference-edit.md` E1–E4 pass containment
- [ ] Reference imported — `validate_reference.py --check-imported` exits 0
- [ ] Bible filled — no `TBD` in `character-bible.md` §1–§11
- [ ] Master prompt filled — no `<...>` slots in `master-character-v1.0.md`
- [ ] `compile_prompt.py --lint` exits 0

PHASE 2.5 matters most here. E4 is a single three-region expression edit; PHASE 3 is
twelve of them. Starting while E4 fails containment reproduces the same failure twelve
times and spends twelve QC cycles discovering it.

---

## 2. Fixed conditions

| Setting    | Value                              | Source                 |
|------------|------------------------------------|------------------------|
| Model      | FLUX.2 Klein 4B **Base**           | `DECISIONS.md` ADR-002 |
| Method     | reference edit from `master.png`    | `DECISIONS.md` ADR-003 |
| Resolution | 1024 x 1024                         | `ASSET_SPEC.md` §1     |
| Batch size | 1                                   | `CLAUDE.md`            |
| Seed       | derived, `10000 + canonical index`  | `prompts/README.md` §4 |
| Edit region| eyes and eyebrows (plus mouth for the three open-mouth expressions) | `PROMPT_GUIDE.md` §4 |
| Denoise    | as low as the change allows         | `PROMPT_GUIDE.md` §4   |

Every expression edits `master.png` — never another expression. Editing a derived asset
compounds drift (`PROMPT_GUIDE.md` §4).

---

## 3. Per-expression loop

```bash
# 1. Compile - never retype a prompt; the compiled text is what metadata records
python3 scripts/generation/compile_prompt.py expressions/happy-v1.0.md
python3 scripts/generation/compile_prompt.py expressions/happy-v1.0.md --json \
  > metadata/prompts/happy-v1.0.json

# 2. Generate in ComfyUI with the workflow in workflows/expression/,
#    using the seed and negative prompt printed above.

# 3. Cut out the background, keeping the flat version as the reproducibility record
#    (ASSET_SPEC 4), then name per ASSET_SPEC 5:
#       character/expressions/narra-expression-happy-v1.png

# 4. Write the sidecar (ASSET_SPEC 11), then validate
python3 scripts/validation/validate_asset.py \
  character/expressions/narra-expression-happy-v1.png --record
```

`validate_asset.py` checks naming, format, alpha, metadata completeness, seed
derivation, and head drift, then prints the visual checklist it cannot judge. A green
automated run is `pending-human-review`, not `approved`.

---

## 4. Set-level QC (PHASE 3.4)

Individual passes are not sufficient. Two of the `ASSET_SPEC.md` §10 criteria are only
answerable across the whole set:

- *legible at 256px*
- *distinct from every other expression in the set*

```bash
python3 scripts/utilities/contact_sheet.py --set expression
```

The sheet renders the reference plus all twelve at 256px on mid grey — chosen because a
white or black background hides an alpha halo at one end of the value range, and a halo
is exactly what QC is looking for.

Review the sheet for:

- [ ] Twelve visibly different expressions — no two read as the same
- [ ] Each legible without reading its label
- [ ] The nine REST-mouth expressions have the same mouth
- [ ] One consistent face across the row — no identity drift
- [ ] Consistent head size and vertical position
- [ ] Lighting direction identical in every cell

The likeliest failures are `friendly` vs `happy`, `serious` vs `proud`, and `concerned`
vs `embarrassed` — each pair differs mainly in brow tension. If a pair is not separable,
strengthen the geometry in the weaker prompt, publish a MINOR version bump, and
regenerate that one asset. Do not regenerate the whole set.

---

## 5. Locking (PHASE 3.5)

```bash
python3 scripts/validation/validate_asset.py --set expression
```

Passes only when all twelve canonical names are present and nothing else is in the
directory. Then, per asset:

1. Automated validation passed.
2. Every visual checklist box ticked by a person.
3. `metadata/validation/<stem>.json` → `human_review.status: approved`, with a reviewer.
4. Sidecar `validation.status` → `approved`.
5. Asset and sidecar committed — approved character assets are committed on explicit
   approval only (`DECISIONS.md` → ADR-006).

Once locked, do not regenerate a successful asset without a reason (`CLAUDE.md`).
A prompt revision after locking is a new version, not an edit in place
(`PROMPT_GUIDE.md` §1).

---

## 6. Failure handling

| Symptom | Action |
|---------|--------|
| Identity drift in one asset | Lower denoise; regenerate that asset only |
| Identity drift across many | Stop. The problem is the workflow or the reference, not the prompts. Re-run PHASE 2.5. |
| Mouth moved on a REST-mouth expression | The edit region is too large — shrink it. This breaks viseme compositing (ADR-004). |
| Two expressions indistinguishable | Strengthen the weaker prompt's geometry; MINOR bump; regenerate one |
| Expression illegible at 256px | Raise intensity one step; stay short of caricature (`PROMPT_GUIDE.md` §5) |
| Head size or position drifted | FAILED regardless of appearance (`ASSET_SPEC.md` §9) |

Every drift observed goes into `character-bible.md` §15 with the fix that resolved it.
Only after a failure is recorded there may a matching negative term be added
(`PROMPT_GUIDE.md` §8) — that ordering keeps the negative prompt short and evidence-based
instead of accumulating superstition.

---

## 7. Results

| Expression | Seed | Generated | Automated QC | Human QC | Locked |
|------------|------|-----------|--------------|----------|--------|
| neutral     | 10000 | NOT RUN | — | — | — |
| friendly    | 10001 | NOT RUN | — | — | — |
| happy       | 10002 | NOT RUN | — | — | — |
| excited     | 10003 | NOT RUN | — | — | — |
| serious     | 10004 | NOT RUN | — | — | — |
| concerned   | 10005 | NOT RUN | — | — | — |
| surprised   | 10006 | NOT RUN | — | — | — |
| confused    | 10007 | NOT RUN | — | — | — |
| thinking    | 10008 | NOT RUN | — | — | — |
| explaining  | 10009 | NOT RUN | — | — | — |
| proud       | 10010 | NOT RUN | — | — | — |
| embarrassed | 10011 | NOT RUN | — | — | — |

Contact sheet: `assets/contact-sheets/narra-sheet-expressions-v1.png`
