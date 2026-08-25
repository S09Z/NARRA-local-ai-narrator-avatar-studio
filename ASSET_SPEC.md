# ASSET_SPEC.md

# NARRA — Asset Specification

Binding technical specification for every generated character asset.
An asset that does not meet this spec does not enter `character/` or `assets/approved/`.

---

## 1. Resolution

| Stage              | Resolution  | Notes                                        |
|--------------------|-------------|----------------------------------------------|
| Iteration          | 1024 x 1024 | Default for all generation and QC             |
| Approved master    | 1024 x 1024 | Locked library resolution                     |
| Upscale (optional) | 2048 x 2048 | Approved assets only, after PHASE 6 lock      |

4K generation is not used during iteration. Upscaling is a post-approval step and never
a substitute for a correct 1024 generation.

## 2. Aspect Ratio

- Character assets: **1:1 square**.
- Every asset in a set shares the same aspect ratio and the same head size in frame,
  so expression and viseme layers stay interchangeable.
- Pose assets may use a wider camera class, but each camera class is internally consistent.

## 3. Image Format

| Purpose                    | Format          |
|----------------------------|-----------------|
| Approved character assets  | PNG, RGBA, 8-bit per channel |
| Contact sheets / review    | PNG or JPG (quality 90+)     |
| Working generations        | PNG                          |

- sRGB color space. No embedded color profile conversions between stages.
- No lossy re-encoding of an approved asset. Edits start from the PNG master.

## 4. Transparency

- Approved character assets are RGBA with a **fully transparent background**
  (alpha 0 outside the character silhouette).
- Alpha edges must be clean: no halo, no matte fringe from a colored background,
  no semi-transparent bleed across the silhouette interior.
- Generation happens on a flat, uniform background; background removal is a separate,
  documented step so the source generation stays reproducible.
- Both the flat-background generation and the RGBA cutout are retained; the cutout is
  the library asset, the flat version is the reproducibility record.

## 5. Naming Convention

All lowercase, kebab-case, no spaces, no Thai characters in filenames.

```
<character>-<type>-<name>-v<version>.png
```

| Type        | Pattern                                    | Example                          |
|-------------|--------------------------------------------|----------------------------------|
| reference   | `<character>-reference-master-v1.png`      | `narra-reference-master-v1.png`  |
| expression  | `<character>-expression-<name>-v1.png`     | `narra-expression-happy-v1.png`  |
| viseme      | `<character>-viseme-<name>-v1.png`         | `narra-viseme-mbp-v1.png`        |
| pose        | `<character>-pose-<name>-v1.png`           | `narra-pose-pointing-left-v1.png`|
| contact sheet | `<character>-sheet-<set>-v1.png`         | `narra-sheet-visemes-v1.png`     |

- Viseme names are lowercased in filenames (`mbp`, `sh`, `kg`) and uppercase in
  documentation and metadata (`MBP`, `SH`, `KG`).
- Version increments on every re-approval. Superseded versions are not deleted silently.
- Every asset has a sidecar metadata file with the same stem: `<stem>.json`.

## 6. Expression Specification

Location: `character/expressions/`
Count required for PHASE 6: **12**

| # | Name        | Carried primarily by                    | Mouth |
|---|-------------|-----------------------------------------|-------|
| 1 | neutral     | relaxed brows, level gaze               | REST  |
| 2 | friendly    | soft eyes, slight brow lift             | REST  |
| 3 | happy       | raised cheeks, narrowed eyes            | REST  |
| 4 | excited     | wide eyes, raised brows                 | open  |
| 5 | serious     | level brows, steady gaze                | REST  |
| 6 | concerned   | inner brows raised, drawn together      | REST  |
| 7 | surprised   | wide eyes, high brows                   | open  |
| 8 | confused    | asymmetric brows, slight head tilt      | REST  |
| 9 | thinking    | gaze off-camera, one brow raised        | REST  |
|10 | explaining  | engaged brows, direct gaze              | open  |
|11 | proud       | lifted chin, relaxed confident brows    | REST  |
|12 | embarrassed | averted gaze, raised inner brows        | REST  |

Requirements:
- Identity, hair, clothing, lighting, and camera identical to the reference.
- Expression is legible at 256px — if it is not readable in a contact sheet thumbnail,
  it is too subtle.
- Each expression is visually distinct from every other expression in the set.
- Expression assets carry a REST mouth unless the table says otherwise, so the viseme
  layer can be composited over them.

## 7. Viseme Specification

Location: `character/visemes/`
Count required for PHASE 6: **16**

Set: `REST, A, I, U, E, O, AE, AO, MBP, FV, TH, KG, S, SH, L, N`

| Viseme | Jaw           | Lips              | Teeth          | Notes                         |
|--------|---------------|-------------------|----------------|-------------------------------|
| REST   | closed        | relaxed, together | hidden         | Neutral idle mouth            |
| A      | wide open     | neutral width     | both visible   | Maximum jaw drop              |
| I      | slightly open | spread wide       | upper visible  | Smile-like spread             |
| U      | slightly open | rounded, forward  | hidden         | Tight rounding                |
| E      | open          | slightly spread   | upper visible  | Between A and I               |
| O      | open          | rounded           | hidden         | Wider rounding than U         |
| AE     | open          | spread            | both visible   | Flat, wide                    |
| AO     | open          | rounded, dropped  | lower visible  | Between A and O               |
| MBP    | closed        | actively pressed  | hidden         | Must differ visibly from REST |
| FV     | slightly open | lower lip tucked  | upper visible  | Upper teeth on lower lip      |
| TH     | slightly open | relaxed           | both visible   | Tongue tip visible            |
| KG     | slightly open | neutral           | slight         | Back-of-mouth, shallow        |
| S      | nearly closed | slightly spread   | both visible   | Narrow gap, teeth close       |
| SH     | slightly open | rounded, forward  | slight         | Protruded, softer than U      |
| L      | open          | neutral           | both visible   | Tongue tip at upper teeth     |
| N      | nearly closed | relaxed           | slight         | Tongue at ridge, near-closed  |

Requirements:
- Only the mouth and jaw region differs from REST. Eyes, eyebrows, gaze, head angle,
  hair, clothing, lighting, and camera are pixel-consistent with the reference.
- MBP vs REST must be distinguishable side by side at 256px.
- All 16 share an identical mouth anchor (§9).
- This is a visual animation approximation for Thai speech, not a phonological model.
  The Thai phoneme→viseme mapping lives in `docs/thai-viseme/`.

## 8. Pose Specification

Location: `character/poses/`
Count required for PHASE 6: **10**

Poses: neutral, explaining, pointing-left, pointing-right, presenting, surprised,
thinking, concerned, confident, excited.

Camera classes: `close-up`, `medium`, `upper-body`, `three-quarter`.

Requirements:
- Head size in frame is consistent within a camera class.
- Hands are either fully in frame or fully out of frame — never cropped mid-hand.
- Face identity is unchanged from the reference.
- Pose name and camera class are both recorded in metadata.

## 9. Mouth Anchor

The mouth anchor is the contract that lets the viseme layer composite onto any
expression or pose asset.

Definition (normalized to image width/height, origin top-left):

```json
{
  "anchor_x": 0.500,
  "anchor_y": 0.640,
  "mouth_width": 0.140,
  "mouth_height": 0.070
}
```

- `anchor_x` / `anchor_y` — center of the mouth opening.
- `mouth_width` / `mouth_height` — bounding box of the mouth region at REST.
- Actual values are measured from the approved reference during PHASE 4.3 and recorded
  in `character/bible/`. The values above are the placeholder structure, not measurements.

Tolerances:
- Anchor drift across visemes: **≤ 0.5% of image width** (≤ 5px at 1024).
- Head vertical drift across any asset in a set: **≤ 1% of image height** (≤ 10px at 1024).
- An asset outside tolerance is FAILED regardless of how good the mouth shape looks.

Every asset's metadata records its measured anchor so drift is detectable automatically.

## 10. Quality Criteria

An asset is APPROVED only if all checks pass. Any single failure = FAILED → regenerate.

Identity:
- [ ] Same person as the reference — face proportions, head shape
- [ ] Eye shape, eye color, and eye position unchanged
- [ ] Eyebrow shape and thickness unchanged
- [ ] Hairstyle, hair color, and hair part unchanged
- [ ] Skin tone unchanged
- [ ] Clothing and accessories unchanged

Render:
- [ ] Art style and line style consistent with the reference
- [ ] Lighting direction and quality unchanged
- [ ] No photorealistic drift, no style bleed
- [ ] No artifacts, no extra limbs, no added text or watermark

Framing:
- [ ] Camera distance and angle match the set
- [ ] Head size and head position within tolerance (§9)
- [ ] Crop is correct; nothing important is cut

Asset class:
- [ ] Expression: target expression legible at 256px and distinct from the rest of the set
- [ ] Viseme: only the mouth changed; anchor within tolerance; MBP distinct from REST
- [ ] Pose: hands intact; head size consistent with camera class

Technical:
- [ ] Resolution and aspect ratio per §1–2
- [ ] PNG RGBA, clean alpha, no halo (§4)
- [ ] Filename matches the naming convention (§5)
- [ ] Sidecar metadata present and complete (§11)

Validation results are recorded in `metadata/validation/`.

## 11. Metadata Requirements

Every approved asset has a sidecar JSON file with the same stem, stored beside the asset
and mirrored into `metadata/generations/`.

```json
{
  "character": "narra",
  "asset_type": "viseme",
  "asset_name": "MBP",
  "version": 1,
  "file": "character/visemes/narra-viseme-mbp-v1.png",
  "reference": "character/reference/narra-reference-master-v1.png",
  "model": {
    "name": "FLUX.2 Klein 4B Base",
    "precision": "fp8",
    "file": "flux2-klein-4b-base-fp8.safetensors"
  },
  "workflow": {
    "file": "workflows/viseme/viseme-reference-edit-v1.json",
    "version": "1.0"
  },
  "prompt": {
    "master_version": "master-character-v1.0",
    "asset_prompt_version": "mbp-v1.0",
    "compiled": "<full compiled prompt text>",
    "negative": "<negative prompt text>"
  },
  "generation": {
    "seed": 20008,
    "steps": 20,
    "cfg": 3.5,
    "sampler": "euler",
    "scheduler": "simple",
    "denoise": 0.45,
    "resolution": [1024, 1024]
  },
  "mouth_anchor": {
    "anchor_x": 0.500,
    "anchor_y": 0.640,
    "mouth_width": 0.140,
    "mouth_height": 0.070
  },
  "environment": {
    "comfyui_version": "",
    "custom_nodes": []
  },
  "validation": {
    "status": "approved",
    "validated_at": "",
    "notes": ""
  },
  "generated_at": ""
}
```

Mandatory fields: `character`, `asset_type`, `asset_name`, `version`, `file`, `reference`,
`model`, `workflow`, `prompt.master_version`, `prompt.asset_prompt_version`,
`generation.seed`, `generation.resolution`, `validation.status`, `generated_at`.

Reproducibility rule: an approved asset must be re-creatable from its metadata alone.
If a field is missing, the asset is not production-locked.
