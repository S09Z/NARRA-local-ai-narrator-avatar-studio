# NARRA — Visual Specification

Version: v0.1 (unfilled)
Status: **AWAITING REFERENCE IMAGE**
Source of truth: `character/reference/narra-reference-master-v1.png`
Companion: `character/bible/character-bible.md` (descriptive) — this file is numeric.

---

## 0. Purpose

The character bible describes the character in words that reach the prompt. This file
records the character in **numbers that can be measured off a rendered image**, so QC is
a measurement rather than an opinion.

Every value marked `TBD` is measured once from the approved reference and then becomes a
tolerance that all 38 library assets (12 expressions + 16 visemes + 10 poses) are held to.

Coordinate convention throughout: **normalized to image width/height, origin top-left**,
x rightward, y downward. Matches `ASSET_SPEC.md` §9.

---

## 1. Canvas

| Property        | Value                     | Source              |
|-----------------|---------------------------|---------------------|
| Resolution      | 1024 x 1024               | `ASSET_SPEC.md` §1  |
| Aspect ratio    | 1:1                       | `ASSET_SPEC.md` §2  |
| Format          | PNG, 8-bit/channel        | `ASSET_SPEC.md` §3  |
| Mode            | RGBA                      | `ASSET_SPEC.md` §4  |
| Color space     | sRGB                      | `ASSET_SPEC.md` §3  |
| Background      | alpha 0 outside silhouette| `ASSET_SPEC.md` §4  |
| Upscale target  | 2048 x 2048, post-lock only | `ASSET_SPEC.md` §1 |

---

## 2. Camera Classes

Head height is the fraction of image height from chin to the top of the hair silhouette.
Consistency *within* a class is what makes assets interchangeable; classes differ from
each other by design.

| Class          | Used by                    | Head height | Crop bottom      | Status |
|----------------|----------------------------|-------------|------------------|--------|
| `close-up`     | reference, expressions, visemes | TBD    | mid-chest        | TBD |
| `medium`       | poses                      | TBD         | waist            | TBD |
| `upper-body`   | poses                      | TBD         | hip              | TBD |
| `three-quarter`| poses                      | TBD         | mid-thigh        | TBD |

The reference, all 12 expressions, and all 16 visemes are `close-up` and share one head
height. Poses may use any class but are internally consistent within it
(`ASSET_SPEC.md` §8).

---

## 3. Face Geometry

Measured from the approved reference. These are the landmarks QC compares against.

| Landmark              | Key           | Value | Status |
|-----------------------|---------------|-------|--------|
| Top of hair silhouette| `hair_top_y`  | TBD   | TBD |
| Top of skull          | `skull_top_y` | TBD   | TBD |
| Eye line (pupil centers)| `eye_y`     | TBD   | TBD |
| Left pupil x          | `eye_l_x`     | TBD   | TBD |
| Right pupil x         | `eye_r_x`     | TBD   | TBD |
| Interpupillary distance| `ipd`        | TBD   | TBD |
| Eyebrow line          | `brow_y`      | TBD   | TBD |
| Nose base             | `nose_y`      | TBD   | TBD |
| Mouth line (lip seam) | `mouth_y`     | TBD   | TBD |
| Chin bottom           | `chin_y`      | TBD   | TBD |
| Face width at cheekbones| `face_w`    | TBD   | TBD |
| Head center x         | `head_cx`     | TBD   | TBD |
| Shoulder line         | `shoulder_y`  | TBD   | TBD |

Derived ratios — these stay constant even if head size changes between camera classes,
which makes them the strongest identity check:

| Ratio                        | Formula                              | Value | Status |
|------------------------------|--------------------------------------|-------|--------|
| Eye line position in head    | `(eye_y - hair_top_y) / head_height` | TBD   | TBD |
| Mouth position in head       | `(mouth_y - eye_y) / (chin_y - eye_y)`| TBD  | TBD |
| Eye spacing in face          | `ipd / face_w`                       | TBD   | TBD |
| Face aspect                  | `(chin_y - skull_top_y) / face_w`    | TBD   | TBD |

---

## 4. Mouth Anchor

The contract that lets a viseme composite onto any expression or pose
(`DECISIONS.md` → ADR-004). Measured at REST from the approved reference and mirrored
into `character/bible/mouth-anchor.json`.

| Field          | Meaning                                | Value | Status |
|----------------|----------------------------------------|-------|--------|
| `anchor_x`     | center x of the mouth opening          | TBD   | TBD |
| `anchor_y`     | center y of the mouth opening          | TBD   | TBD |
| `mouth_width`  | mouth bounding box width at REST       | TBD   | TBD |
| `mouth_height` | mouth bounding box height at REST      | TBD   | TBD |

### Permitted edit region

Recorded alongside the anchor as `edit_region` in `mouth-anchor.json`: the normalized box
the reference-edit workflow may touch, and the box `validate_asset.py` holds a viseme's
changed pixels inside (`DECISIONS.md` → ADR-013).

| Field    | Meaning                              | Value | Status |
|----------|--------------------------------------|-------|--------|
| `left`   | left edge of the mask region         | TBD   | TBD |
| `top`    | top edge                             | TBD   | TBD |
| `right`  | right edge                           | TBD   | TBD |
| `bottom` | bottom edge                          | TBD   | TBD |

It is deliberately asymmetric about the anchor — much taller below than above — because a
viseme opens the jaw downward. `A` is the maximum drop in the set and needs the room; a
symmetric box either clips it or reaches the eyes.

Tolerances (`ASSET_SPEC.md` §9) — binding, and independent of how good the mouth looks:

| Tolerance                          | Limit                  | At 1024 |
|------------------------------------|------------------------|---------|
| Anchor drift across visemes        | ≤ 0.5% of image width  | ≤ 5 px  |
| Head vertical drift across a set   | ≤ 1% of image height   | ≤ 10 px |

The placeholder values in `ASSET_SPEC.md` §9 (`0.500 / 0.640 / 0.140 / 0.070`) are
structure, not measurements. They are replaced by real values in PHASE 4.3 and must not
be treated as approved until then.

---

## 5. Color Palette

Hex values sampled from the approved reference, sRGB. These are the values a QC script
compares against; `character-bible.md` holds the prose description.

| Slot              | Key                | Hex | Status |
|-------------------|--------------------|-----|--------|
| Skin base         | `skin_base`        | TBD | TBD |
| Skin shadow       | `skin_shadow`      | TBD | TBD |
| Skin highlight    | `skin_highlight`   | TBD | TBD |
| Blush             | `skin_blush`       | TBD | TBD |
| Hair base         | `hair_base`        | TBD | TBD |
| Hair shadow       | `hair_shadow`      | TBD | TBD |
| Hair highlight    | `hair_highlight`   | TBD | TBD |
| Iris              | `iris`             | TBD | TBD |
| Sclera            | `sclera`           | TBD | TBD |
| Eyebrow           | `brow`             | TBD | TBD |
| Lip               | `lip`              | TBD | TBD |
| Inner mouth       | `mouth_inner`      | TBD | TBD |
| Teeth             | `teeth`            | TBD | TBD |
| Clothing primary  | `cloth_primary`    | TBD | TBD |
| Clothing secondary| `cloth_secondary`  | TBD | TBD |
| Line color        | `line`             | TBD | TBD |

Sampling rule: sample a flat lit region, not an edge or a gradient, and record the
sample coordinate alongside the value so it is repeatable.

Tolerance: mean hue drift of a sampled region **≤ 3°**, lightness drift **≤ 4%**.
Beyond that, the asset fails the "skin tone unchanged" / "hair color unchanged" checks in
`ASSET_SPEC.md` §10.

---

## 6. Line and Shading

| Property               | Value | Status |
|------------------------|-------|--------|
| Outline present        | TBD   | TBD |
| Outline weight (px @1024)| TBD | TBD |
| Interior line weight   | TBD   | TBD |
| Line color treatment   | TBD   | TBD |
| Shading bands          | TBD   | TBD |
| Shadow edge hardness   | TBD   | TBD |
| Specular highlights    | TBD   | TBD |
| Texture / grain        | TBD   | TBD |

Line weight is measured in pixels at 1024 so that a style drift toward thin, sketchy, or
photorealistic rendering is detectable numerically instead of by eye.

---

## 7. Lighting Rig

| Property          | Value | Status |
|-------------------|-------|--------|
| Key direction     | TBD   | TBD |
| Key elevation     | TBD   | TBD |
| Key softness      | TBD   | TBD |
| Fill ratio        | TBD   | TBD |
| Rim light         | TBD   | TBD |
| Shadow side       | TBD   | TBD |
| Terminator position on face | TBD | TBD |

Key direction is the most detectable lighting drift: if the shadow side flips between two
assets, they cannot be intercut and both fail framing QC.

---

## 8. Alpha and Edge

| Property               | Requirement                                  |
|------------------------|----------------------------------------------|
| Background alpha       | exactly 0                                    |
| Silhouette interior alpha | exactly 255, no semi-transparent bleed    |
| Edge transition        | ≤ 2 px of antialiasing                       |
| Halo / matte fringe    | none — no residue of the generation background|
| Premultiplication      | not premultiplied; straight alpha             |

Generation happens on a flat background and cutout is a separate documented step
(`ASSET_SPEC.md` §4). Both files are retained: the cutout is the library asset, the flat
version is the reproducibility record.

---

## 9. Measurement Procedure

Landmarks are recorded once, by hand, from the approved reference — there is no automatic
landmark detector in this project and adding one is not justified for a single image.

1. Open the approved reference at 1024 x 1024, 100% zoom, no scaling.
2. Read pixel coordinates for each landmark in §3.
3. Divide by 1024 and record to 3 decimal places.
4. Sample §5 colors from flat lit regions; record the sample coordinate with each value.
5. Record the mouth box with `python3 scripts/utilities/measure_anchor.py --box L T R B`,
   which writes the four anchor values and the `edit_region` into `mouth-anchor.json`.
6. Set every touched `Status` cell to `LOCKED` and bump this file to v1.0.
7. Record the version bump in `character-bible.md` §16.

Once locked, these values are compared against — not re-derived. A later asset that
disagrees with them is the thing that is wrong.
