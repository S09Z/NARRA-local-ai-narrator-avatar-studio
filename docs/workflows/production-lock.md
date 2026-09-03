# Production Lock Runbook — PHASE 6

Status: **NOT RUN** — no assets generated; blocked on the PHASE 0–5 gates
Gate: `scripts/validation/lock_library.py`
Lock: `metadata/production-lock.json`
Baseline: `docs/production-baseline.md` (generated — do not edit by hand)

---

## 1. What PHASE 6 is

PHASE 6 is not a generation phase. Nothing new is produced; the 38 assets from PHASE 3–5
are either complete, correct, signed for, and reproducible from their own metadata, or
they are not. `PLAN.md` calls it the IMAGE PIPELINE GATE: no lip-sync, TTS, phoneme
analysis, HyperFrames, or video work begins until this exits 0.

The gate is deliberately unforgiving in one direction only. It can fail an asset a person
would have approved; it cannot approve an asset a person never looked at
(`DECISIONS.md` → ADR-016).

---

## 2. Before starting

- [ ] PHASE 0–5 gates passed
- [ ] Reference imported — `validate_reference.py --check-imported` exits 0
- [ ] Mouth anchor and edit region measured — `measure_anchor.py --show`
- [ ] 12 expressions, 16 visemes, 10 poses in `character/`, each with a sidecar
- [ ] `compile_prompt.py --lint` exits 0
- [ ] `validate_compositions.py` exits 0

Running the gate before any of this is useful — it prints exactly what is missing, and it
writes nothing:

```
python3 scripts/validation/lock_library.py
```

---

## 3. The loop

### 3.1 Complete each set (PLAN 6.1)

```
python3 scripts/validation/validate_asset.py --set expression
python3 scripts/validation/validate_asset.py --set viseme
python3 scripts/validation/validate_asset.py --set pose
```

The locked library holds exactly the canonical set: a missing asset and an extra one are
both failures. Names and seeds come from `scripts/lib/canon.py`.

### 3.2 Build the review sheets (PLAN 6.2)

```
python3 scripts/utilities/contact_sheet.py --all
```

Three sheets, at the paths the gate checks. Build them *after* the last regeneration —
the gate warns when a sheet is older than an asset it claims to show, because a review of
a stale sheet is a review of a different image.

### 3.3 Validate and sign off each asset

```
python3 scripts/validation/validate_asset.py character/visemes/narra-viseme-mbp-v1.png
```

Fix every FAIL first. The automated half is not an approval — it prints the
`ASSET_SPEC.md` §10 checklist a person has to judge from the contact sheet: identity, hair,
clothing, lighting, expression legibility at 256px, MBP against REST, hands in or out.

When those hold, record the sign-off:

```
python3 scripts/validation/validate_asset.py <asset> --approve "your name" --notes "..."
```

That writes `metadata/validation/<stem>.json` with `overall: approved`. The gate reads
that file. A sign-off is refused over a failed check.

### 3.4 Run the gate

```
python3 scripts/validation/lock_library.py
```

Exit 0 means every requirement below is met. Exit 1 lists each blocking problem with the
spec section it comes from.

### 3.5 Lock (PLAN 6.4, 6.5)

```
python3 scripts/validation/lock_library.py --lock --by "your name"
```

This is the only step that writes. It produces `metadata/production-lock.json`, mirrors
each sidecar into `metadata/generations/` (`ASSET_SPEC.md` §11), and regenerates
`docs/production-baseline.md` from the asset metadata.

---

## 4. What the gate checks

| Check | Requirement | Source |
|-------|-------------|--------|
| `canon/*` | the canonical sets still hold 12 / 16 / 10 names | PLAN 6.1 |
| `reference/master` | imported, alias byte-identical, sidecar sha256 matches | PHASE 1.1, ADR-008 |
| `anchor/*` | mouth anchor and edit region measured | PHASE 4.3, ADR-013 |
| `<set>/complete` | every canonical asset present, nothing extra | PLAN 6.1 |
| `<set>/<name>` | naming, format, alpha, metadata, seed, drift, containment, sign-off | ASSET_SPEC 5–11 |
| `framing/<class>` | pose crown positions agree within a camera class | ASSET_SPEC 8, ADR-018 |
| `sheet/<set>` | a review sheet exists, and is not older than its assets | PLAN 6.2 |
| `compositions` | narrator states still resolve to real assets | PLAN 5.3 |
| `upscale/*` | derivatives name the locked master they came from | ASSET_SPEC 1, ADR-017 |

---

## 5. Resolution and upscales (PLAN 6.3)

The locked library is 1024x1024. That is enforced twice: the PNG header, and the
`generation.resolution` recorded in the sidecar — an asset generated at another size and
resampled afterwards fails on the second.

Upscaling is optional and happens only after the lock. An upscale is a derivative:
`assets/approved/upscaled/<master-stem>-up2048.png`, with a sidecar naming
`derived_from` and the master's `derived_from_sha256`. It is never the input to a further
edit — edits start from the 1024 master (`ASSET_SPEC.md` §1, ADR-017).

---

## 6. After the lock

```
python3 scripts/validation/lock_library.py --verify
```

Re-hashes every locked asset against the lock. Run it before any PHASE 7+ work that
assumes the library, and after anything that touched `character/`.

What invalidates the lock:

- regenerating any locked asset
- re-importing the reference
- re-measuring the mouth anchor
- bumping a prompt or workflow version an asset records

Any of those means: fix the assets, re-review what changed, re-run the gate, re-lock. The
lock version increments; the old lock is replaced, not kept — git history holds the
previous one.

`CLAUDE.md`: do not regenerate a successful asset without a reason.

---

## 7. Failure modes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `no QC record` | validated but never signed off | `validate_asset.py <asset> --approve "name"` |
| `not approved` | recorded as `pending-human-review` | review against the contact sheet, then `--approve` |
| `mirror ... differs from the sidecar` | sidecar edited after a lock | re-run the gate and re-lock |
| `crown spread ... max 1%` | two poses in one class framed differently | regenerate the outlier, not the tolerance |
| `edit escaped the mouth region` | a viseme changed more than the mouth | stronger preservation wording, lower denoise (`PROMPT_GUIDE.md` §6) |
| `is not in the canonical ... set` | a stray or experimental file in `character/` | move it to `assets/generated/` |
| `sheet ... is older than` | assets regenerated after the sheet | `contact_sheet.py --all` |
| `sha256 differs from the lock` | a locked asset was edited in place | restore it, or re-run the gate and re-lock |

---

## 8. Exit criteria

- [ ] `lock_library.py` exits 0
- [ ] `metadata/production-lock.json` written, 38 assets, every one with a reviewer
- [ ] `docs/production-baseline.md` shows **LOCKED**
- [ ] `lock_library.py --verify` exits 0
- [ ] `MEMORY.md` and `DECISIONS.md` updated

PHASE 7 opens only when all five hold.
