# character/reference/ — Canonical Reference

This directory holds the single source of truth for the NARRA character.
Everything in `character/expressions/`, `character/visemes/`, and `character/poses/`
is derived from the file here by reference editing (`DECISIONS.md` → ADR-003).

---

## 1. Files

| File                            | Role                                                        |
|---------------------------------|-------------------------------------------------------------|
| `narra-reference-master-v1.png` | Versioned canonical master. The real artifact.               |
| `narra-reference-master-v1.json`| Sidecar metadata (`ASSET_SPEC.md` §11).                      |
| `master.png`                    | Stable alias for the current master. Byte-identical copy.    |

Why both: `ASSET_SPEC.md` §5 requires a versioned filename; `PLAN.md` §1.1 and
`PROMPT_GUIDE.md` §4 refer to a stable `master.png` path that workflows can hardcode.
Both are kept. See `DECISIONS.md` → ADR-008.

`master.png` is a **copy**, not a symlink, so ComfyUI resolves it identically on
Windows, Linux, and macOS. `scripts/validation/validate_reference.py` enforces that the
copy is byte-identical to the versioned master.

---

## 2. Requirements for the reference image

Binding — a candidate that fails any of these is not imported.

| Check           | Requirement                                                    |
|-----------------|----------------------------------------------------------------|
| Resolution      | 1024 x 1024 (`ASSET_SPEC.md` §1)                                |
| Aspect ratio    | 1:1 square (`ASSET_SPEC.md` §2)                                 |
| Format          | PNG, 8-bit per channel (`ASSET_SPEC.md` §3)                     |
| Mode            | RGBA (`ASSET_SPEC.md` §4)                                       |
| Background      | Fully transparent outside the silhouette, clean alpha edges     |
| Color space     | sRGB, no embedded profile conversion                            |
| Framing         | Head fully in frame, no crop of hair or chin                    |
| Mouth           | REST mouth — relaxed, closed. This is the anchor for all 16 visemes |
| Gaze            | At camera                                                       |
| Head angle      | Front-facing or a single fixed three-quarter angle, held forever |
| Expression      | Neutral                                                         |

The reference is generated on a flat, uniform background; the RGBA cutout is the library
asset and the flat-background generation is retained as the reproducibility record
(`ASSET_SPEC.md` §4). Store the flat version as
`assets/input/narra-reference-master-v1-flat.png`.

Two properties matter more than aesthetics, because every later phase inherits them:

1. **REST mouth.** All 16 visemes are edits of this mouth. A reference caught mid-smile
   makes every viseme fight the source.
2. **Head position and size.** The mouth anchor (`ASSET_SPEC.md` §9) is measured from this
   image once and every derived asset is held to it within 0.5% of image width.

---

## 3. Import procedure (PHASE 1.1)

```bash
# 1. Put the candidate anywhere, e.g. assets/input/candidate.png
# 2. Validate it against the spec (does not write anything)
python3 scripts/validation/validate_reference.py assets/input/candidate.png

# 3. If it passes, import it — writes the versioned master, master.png, and the sidecar
python3 scripts/validation/validate_reference.py assets/input/candidate.png --import

# 4. Verify the imported state
python3 scripts/validation/validate_reference.py --check-imported
```

After import:

1. Fill `character/bible/character-bible.md` from the image — every field marked `TBD`.
2. Fill the measured values in `character/bible/visual-spec.md` and
   `character/bible/mouth-anchor.json`.
3. Run the PHASE 1.4 baseline tests (`tests/assets/phase1-baseline.md`).

---

## 4. Change control

Replacing the reference invalidates every derived asset in the library.

- A new reference is a new version: `narra-reference-master-v2.png`. The v1 file is not
  deleted.
- Bumping the reference version requires an ADR entry in `DECISIONS.md` stating why.
- After a reference bump, every expression, viseme, and pose is regenerated. There is no
  partial migration — mixed-reference assets will not composite.
