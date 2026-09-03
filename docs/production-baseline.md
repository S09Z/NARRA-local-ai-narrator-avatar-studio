# PRODUCTION BASELINE

PHASE 6.5 — the exact configuration the locked image library was produced with.

**Generated file.** Written by `scripts/validation/lock_library.py`; every value
below is read from the asset metadata, not typed in. Do not edit it by hand — the
next lock overwrites it. To change a value here, regenerate the asset and re-lock.

## Status

**NOT LOCKED.** No `metadata/production-lock.json` has been written, so there
is no baseline to record. PHASE 7 (Thai audio / phoneme) and everything after it
remain blocked (PLAN.md — IMAGE PIPELINE GATE).

To reach the lock:

```
python3 scripts/validation/lock_library.py            # what is still missing
python3 scripts/utilities/contact_sheet.py --all      # PLAN 6.2 review sheets
python3 scripts/validation/validate_asset.py <asset> --approve "name"
python3 scripts/validation/lock_library.py --lock --by "name"
```

The gate requires, in order: an imported reference, a measured mouth anchor,
12 expressions, 16 visemes, 10 poses, a contact sheet per set, valid narrator
compositions, and a recorded human sign-off for every asset.
