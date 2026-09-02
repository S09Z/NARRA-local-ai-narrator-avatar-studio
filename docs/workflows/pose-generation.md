# Pose Generation Runbook — PHASE 5

Status: **NOT RUN** — blocked on the PHASE 0, PHASE 1, and PHASE 2.5 gates
Prompts: `prompts/poses/<name>-v1.0.md` — 10 files, complete
Compositions: `character/compositions/narrator-states.json`
Output: `character/poses/` on approval

---

## 1. What makes poses different

Expressions and visemes hold the whole frame still and change one small region. Poses do
the opposite: the body and the camera both move, and only the face is held.

Two consequences:

1. **The camera class is part of the asset.** A pose is not just a body position; it is a
   body position at a stated framing (`ASSET_SPEC.md` §8), and the class is recorded in
   metadata alongside the name.
2. **Hands are the failure mode.** `PROMPT_GUIDE.md` §7 names them the highest-failure
   region, and the specific failure is a hand cropped at the wrist. The rule is all in or
   all out — never partly.

`PLAN.md` §5 defines no QC or lock milestone of its own. The requirements come from
`ASSET_SPEC.md` §8 and the generic quality gate in §10.

---

## 2. Camera classes (PHASE 5.2)

| Class | Crop bottom | Hands | Used by |
|-------|-------------|-------|---------|
| `close-up` | mid-chest | out of frame | reference, expressions, visemes |
| `medium` | waist | out of frame | `neutral`, `explaining`, `surprised`, `thinking`, `concerned` |
| `upper-body` | hip | **fully in frame** | `pointing-left`, `pointing-right`, `presenting`, `excited` |
| `three-quarter` | mid-thigh | **fully in frame** | `confident` |

Head height per class is specified in `character/bible/visual-spec.md` §2 as a **ratio to
the close-up head height**, not an absolute. That is what makes the classes definable
before the reference is measured: once `close-up` is known, each class is
`close-up × ratio`, and no class has to be re-derived (`DECISIONS.md` → ADR-014).

Tolerance within a class: head height varies by ≤ 2% of image height (≤ 20px at 1024).
Two poses in the same class that fall outside that cannot be intercut. Differences
*across* classes are intentional and are not defects.

The five gesture-free poses are `medium` on purpose. A pose that keeps its hands below the
frame edge cannot fail the hand-crop check, so the four poses that genuinely need hands
are the only ones carrying that risk.

---

## 3. Before starting

- [ ] PHASE 0, PHASE 1, PHASE 2.5 gates passed
- [ ] Reference imported; bible and master prompt filled
- [ ] `close-up` head height measured in `visual-spec.md` §2, so the per-class targets resolve
- [ ] `compile_prompt.py --lint` exits 0
- [ ] `validate_compositions.py` exits 0

---

## 4. Fixed conditions

| Setting    | Value                                | Source                 |
|------------|--------------------------------------|------------------------|
| Model      | FLUX.2 Klein 4B **Base**             | `DECISIONS.md` ADR-002 |
| Method     | reference edit from `master.png`      | `DECISIONS.md` ADR-003 |
| Resolution | 1024 × 1024                           | `ASSET_SPEC.md` §1     |
| Seed       | derived, `30000 + canonical index`    | `prompts/README.md` §4 |
| Edit region| body and arms; head region untouched  | `PROMPT_GUIDE.md` §4   |

Poses change the camera as well as the body, so the framing group of negatives is
deliberately omitted for this asset class — `changed camera distance` would fight the
prompt (`PROMPT_GUIDE.md` §8). The face is protected by the PRESERVATION block instead.

---

## 5. Per-pose loop

```bash
python3 scripts/generation/compile_prompt.py poses/pointing-left-v1.0.md
python3 scripts/generation/compile_prompt.py poses/pointing-left-v1.0.md --json \
  > metadata/prompts/pointing-left-v1.0.json

# generate, cut out, name per ASSET_SPEC 5:
#   character/poses/narra-pose-pointing-left-v1.png
# write the sidecar, including camera_class, then:

python3 scripts/validation/validate_asset.py \
  character/poses/narra-pose-pointing-left-v1.png --record
```

For a pose the validator additionally checks that the sidecar records a `camera_class`,
that it is one of the four, and that it **matches what the pose prompt declares**. An
asset framed differently from the prompt it records is not reproducible from its metadata,
which is the whole point of recording it.

Suggested order: the five `medium` poses first — no hands, so they isolate whether the
body edit preserves the face. Then `confident`, then the four hand-bearing poses last,
since those are where regeneration effort will go.

---

## 6. QC (`ASSET_SPEC.md` §8, §10)

```bash
python3 scripts/utilities/contact_sheet.py --set pose
python3 scripts/validation/validate_asset.py --set pose
```

`--set pose` prints each pose with its camera class, so the set can be read class by class
rather than as ten unrelated images.

Per asset:

- [ ] Face identity unchanged from the reference — this is the whole constraint
- [ ] Hands fully in frame **or** fully out of frame, never cropped mid-hand
- [ ] Correct number of fingers; no fused or extra digits
- [ ] Head size consistent with the other poses in the same camera class
- [ ] Crop line matches the class — waist for `medium`, hip for `upper-body`
- [ ] Clothing unchanged, including collar and neckline
- [ ] Lighting direction unchanged

Across the set:

- [ ] `pointing-left` and `pointing-right` are true mirrors, not two different gestures
- [ ] The five `medium` poses share one head size
- [ ] The four `upper-body` poses share one head size
- [ ] No pose has drifted toward a different person

---

## 7. Narrator compositions (PHASE 5.3)

`character/compositions/narrator-states.json` defines five reusable states as recipes over
the layers, not as new assets:

| State | Pose | Expression | Mouth |
|-------|------|------------|-------|
| `talking` | `neutral` | `neutral` | viseme-track |
| `explaining` | `explaining` | `friendly` | viseme-track |
| `presenting` | `presenting` | `happy` | viseme-track |
| `reaction` | `surprised` | `surprised` | static |
| `emphasis` | `excited` | `excited` | static |

```bash
python3 scripts/validation/validate_compositions.py
```

The rule that shapes this table: **an open-mouth expression cannot host a viseme track.**
`excited`, `surprised`, and `explaining` carry their own open mouths
(`ASSET_SPEC.md` §6), so compositing a viseme over them would render two mouths. The two
states built on them are therefore non-speaking beats, and the `explaining` *state* uses
the `friendly` expression rather than the `explaining` one. The validator fails any state
that breaks this.

That constraint is not a limitation to work around — it is what keeps the three speaking
states genuinely reusable across every sentence of narration.

---

## 8. Failure handling

| Symptom | Action |
|---------|--------|
| Hand cropped at the wrist | FAILED. Widen the framing or move the gesture inward; regenerate. |
| Extra or fused fingers | Regenerate with a different seed offset **only** as a last resort — it breaks seed derivation, so record the deviation in metadata |
| Face drifted | The edit region reached the head. Constrain it and regenerate. |
| Head size differs within a class | FAILED — the two cannot be intercut (`visual-spec.md` §2) |
| `pointing-left`/`-right` not mirrored | Regenerate the weaker one against the stronger one's framing |
| Crop line wrong for the class | Framing error, not a pose error. Fix the CAMERA block; MINOR bump. |

---

## 9. Results

| Pose | Seed | Camera class | Generated | Hands | Human QC | Locked |
|------|------|--------------|-----------|-------|----------|--------|
| neutral        | 30000 | medium        | NOT RUN | — | — | — |
| explaining     | 30001 | medium        | NOT RUN | — | — | — |
| pointing-left  | 30002 | upper-body    | NOT RUN | — | — | — |
| pointing-right | 30003 | upper-body    | NOT RUN | — | — | — |
| presenting     | 30004 | upper-body    | NOT RUN | — | — | — |
| surprised      | 30005 | medium        | NOT RUN | — | — | — |
| thinking       | 30006 | medium        | NOT RUN | — | — | — |
| concerned      | 30007 | medium        | NOT RUN | — | — | — |
| confident      | 30008 | three-quarter | NOT RUN | — | — | — |
| excited        | 30009 | upper-body    | NOT RUN | — | — | — |

Contact sheet: `assets/contact-sheets/narra-sheet-poses-v1.png`
