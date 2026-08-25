# Viseme Generation Runbook — PHASE 4.4 / 4.6

Status: **NOT RUN** — blocked on the PHASE 0, PHASE 1, and PHASE 2.5 gates
Prompts: `prompts/visemes/<name>-v1.0.md` — 16 files, complete
Mapping: `docs/thai-viseme/thai-viseme-mapping.md`
Output: `character/visemes/` on approval

---

## 1. Why this is the strictest phase

Every viseme is the same face with a different mouth. That is not a stylistic preference —
`DECISIONS.md` → ADR-004 composites a mouth track over an expression track at animation
time, and that only works if all sixteen mouths sit at the same anchor on the same face.

The failure mode is quiet. A viseme set can look fine one image at a time and still be
unusable, because the faces underneath drift by a few pixels each and the mouths land in
sixteen slightly different places. `ASSET_SPEC.md` §9 caps that at 0.5% of image width —
5px at 1024 — and the cap is binding regardless of how good a mouth shape looks.

---

## 2. Before starting

- [ ] PHASE 0 gate — ComfyUI launches, Klein 4B loads, test image succeeds
- [ ] PHASE 1 gate — baseline tests B1–B3 pass
- [ ] PHASE 2.5 — E3 (`change only the mouth`) passes containment
- [ ] PHASE 3 — expression set locked, or at least E4 passing
- [ ] Reference imported — `validate_reference.py --check-imported` exits 0
- [ ] Bible and master prompt filled — no `TBD`, no `<...>`
- [ ] **Mouth anchor measured** — `measure_anchor.py --show` reports `measured`
- [ ] `compile_prompt.py --lint` exits 0

PHASE 2.5 E3 is the direct precursor: one mouth edit that must not disturb the eyes. This
phase is that same edit sixteen times. If E3 leaks into the eyes or brows, so will all
sixteen.

---

## 3. Measure the mouth anchor first (PHASE 4.3)

Nothing else in this phase can be validated until this exists.

1. Open the approved reference at 1024×1024, 100% zoom, no scaling.
2. Read the pixel bounding box of the **REST** mouth — the outer edge of the lips.
3. Record it:

```bash
python3 scripts/utilities/measure_anchor.py --box LEFT TOP RIGHT BOTTOM
python3 scripts/utilities/measure_anchor.py --show
```

This writes `anchor_x`, `anchor_y`, `mouth_width`, `mouth_height`, and an `edit_region`
to `character/bible/mouth-anchor.json`. The tool checks the numbers are plausible — a
mouth in the upper half of a close-up frame is the eye line, not the mouth — but it
cannot find the mouth for you. There is no landmark detector in this project and one is
not justified for a single image.

The `edit_region` is the mask the workflow is allowed to touch. It is derived wider and
much taller than the resting mouth because a viseme opens the jaw *downward*: `A` is the
maximum drop in the set and needs room below the lip line. Override it with
`--edit-region` if the workflow's mask differs.

Then copy the values into `character/bible/visual-spec.md` §4 and set its status cells to
`LOCKED`. From that point the anchor is compared against, never re-derived.

---

## 4. Fixed conditions

| Setting     | Value                                   | Source                 |
|-------------|-----------------------------------------|------------------------|
| Model       | FLUX.2 Klein 4B **Base**                | `DECISIONS.md` ADR-002 |
| Method      | reference → mouth mask → edit           | `PLAN.md` §4.4         |
| Mask        | `edit_region` from `mouth-anchor.json`   | PHASE 4.3              |
| Resolution  | 1024 × 1024                              | `ASSET_SPEC.md` §1     |
| Seed        | derived, `20000 + canonical index`       | `prompts/README.md` §4 |
| Denoise     | as low as the shape allows               | `PROMPT_GUIDE.md` §4   |

Every viseme edits `master.png`. Never generate `A` by editing `E` — editing a derived
asset compounds drift, and with sixteen assets the compounding is what destroys the set.

If a viseme needs a high denoise before the shape appears, the prompt is wrong, not the
strength (`PROMPT_GUIDE.md` §4).

---

## 5. Per-viseme loop

```bash
python3 scripts/generation/compile_prompt.py visemes/mbp-v1.0.md
python3 scripts/generation/compile_prompt.py visemes/mbp-v1.0.md --json \
  > metadata/prompts/mbp-v1.0.json

# generate, cut out, name per ASSET_SPEC 5:
#   character/visemes/narra-viseme-mbp-v1.png
# write the sidecar (ASSET_SPEC 11), including the measured mouth_anchor, then:

python3 scripts/validation/validate_asset.py \
  character/visemes/narra-viseme-mbp-v1.png --record
```

For a viseme the validator additionally runs **containment**: it diffs the asset against
the reference and checks that every changed pixel falls inside `edit_region`. That turns
"change only the mouth" from a matter of opinion into a measurement — if the eyes moved,
the changed-region bounding box extends above the mouth region and the asset fails, with
the overshoot reported in pixels.

To inspect what an edit actually touched:

```bash
python3 scripts/utilities/measure_anchor.py --from-diff \
  character/reference/master.png character/visemes/narra-viseme-mbp-v1.png
```

Suggested order: `REST` first, since it is the closest to the reference and proves the
pipeline; then `MBP`, because it is the one that most often fails; then the open vowels
`A E O AE AO`, then `I U SH`, then the consonants `FV TH KG S L N`.

---

## 6. Set-level QC (PHASE 4.5)

```bash
python3 scripts/utilities/contact_sheet.py --set viseme
```

Sixteen mouths plus the reference at 256px. Check:

- [ ] One identical face in every cell — eyes, brows, gaze, head angle
- [ ] **`MBP` distinguishable from `REST`** — the single most important pair in the set
- [ ] `U` vs `O` vs `SH` separable — all three are rounded
- [ ] `I` vs `AE` separable — both are spread
- [ ] `E` vs `L` separable — `L` differs only by a visible tongue tip
- [ ] `N` vs `S` vs `KG` separable — all three are nearly closed
- [ ] Mouth centres all in the same place; only the shape differs
- [ ] Lighting direction identical in every cell

Those five pairs are where this set fails. Each is two shapes that differ by one feature,
and if the prompt's descriptor is vague the model produces the same mouth twice.

`MBP` vs `REST` is the one to fail the phase over. `REST` is a relaxed closed mouth;
`MBP` is an actively pressed one. If a reviewer cannot tell them apart side by side,
**both fail** (`ASSET_SPEC.md` §7) — and since `MBP` covers /b p pʰ m/ plus final /p̚/,
which is the heaviest consonant load in Thai, every bilabial in the language would render
as an idle mouth.

---

## 7. Locking (PHASE 4.6)

```bash
python3 scripts/validation/validate_asset.py --set viseme
```

Passes only when all sixteen canonical names are present and nothing else is in the
directory. Then per asset: automated checks passed, every visual box ticked by a person,
`metadata/validation/<stem>.json` marked approved with a reviewer, sidecar
`validation.status` set to `approved`, and the asset committed (`DECISIONS.md` → ADR-006).

---

## 8. Failure handling

| Symptom | Action |
|---------|--------|
| Containment fails upward | Mask region too tall — the edit is reaching the eyes. Shrink `edit_region`. |
| Containment fails downward on `A` | Mask too short for maximum jaw drop — extend `edit_region` down and re-measure |
| Anchor drift beyond 0.5% | FAILED regardless of the shape. The mouth is in the wrong place. |
| `MBP` looks like `REST` | Strengthen the compression language; MINOR bump; regenerate both and re-compare |
| Two rounded visemes identical | Make the width and protrusion values explicitly different between them |
| `L` reads as `E` | The tongue tip is missing — it is the entire difference |
| Face drifts across the set | Stop. Do not generate the remaining visemes. Re-run PHASE 2.5 E3. |

Record every drift in `character-bible.md` §15 with the fix. A negative term may only be
added after a failure is recorded there (`PROMPT_GUIDE.md` §8).

---

## 9. Results

| Viseme | Seed | Generated | Containment | Anchor | Human QC | Locked |
|--------|------|-----------|-------------|--------|----------|--------|
| REST | 20000 | NOT RUN | — | — | — | — |
| A    | 20001 | NOT RUN | — | — | — | — |
| I    | 20002 | NOT RUN | — | — | — | — |
| U    | 20003 | NOT RUN | — | — | — | — |
| E    | 20004 | NOT RUN | — | — | — | — |
| O    | 20005 | NOT RUN | — | — | — | — |
| AE   | 20006 | NOT RUN | — | — | — | — |
| AO   | 20007 | NOT RUN | — | — | — | — |
| MBP  | 20008 | NOT RUN | — | — | — | — |
| FV   | 20009 | NOT RUN | — | — | — | — |
| TH   | 20010 | NOT RUN | — | — | — | — |
| KG   | 20011 | NOT RUN | — | — | — | — |
| S    | 20012 | NOT RUN | — | — | — | — |
| SH   | 20013 | NOT RUN | — | — | — | — |
| L    | 20014 | NOT RUN | — | — | — | — |
| N    | 20015 | NOT RUN | — | — | — | — |

Contact sheet: `assets/contact-sheets/narra-sheet-visemes-v1.png`
