# NARRA — Character Bible

Version: v0.1 (unfilled)
Status: **AWAITING REFERENCE IMAGE**
Source of truth: `character/reference/narra-reference-master-v1.png`
Consumed by: `prompts/master/master-character-v1.0.md` (PHASE 2.1)

---

## 0. How this document works

This is the canonical written description of the character. `PROMPT_GUIDE.md` §2 builds
the master prompt directly from it, so every field here becomes prompt text that is
repeated in every single generation for the life of the project.

**Fill rules:**

1. The reference image is authoritative. Every field marked `TBD` is *observed* from
   the image, not invented. If the image and this document disagree, the image wins and
   this document is corrected.
2. Fields marked `PROPOSED` are not visible in the image (personality, narrator role).
   They are drafted here and become binding once confirmed.
3. Write concrete visual geometry, not adjectives. FLUX renders "eyebrows sit high with
   a soft arch, thickness even from inner to outer end"; it does not render "nice eyebrows".
4. One fact per field. If a field needs a sentence of hedging, it is not observed yet.
5. Never delete a filled field to change it — bump the document version and record the
   change in §14.

**Status legend:** `TBD` = must be observed from the reference · `PROPOSED` = drafted,
awaiting confirmation · `LOCKED` = filled and in use by approved assets.

The `Prompt block` column maps each section to its destination block in
`PROMPT_GUIDE.md` §1.

---

## 1. Identity Summary

Prompt block: `CHARACTER`

| Field           | Value | Status |
|-----------------|-------|--------|
| Character id    | `narra` | LOCKED |
| Display name    | TBD   | TBD |
| Apparent age    | TBD   | TBD |
| Build           | TBD   | TBD |
| Ethnicity read  | Thai  | PROPOSED |
| Role            | Narrator / presenter for Thai-language content | PROPOSED |

One-line identity sentence (this line opens the master prompt):

> TBD — e.g. "A Thai narrator, <age>, <build>, <one distinguishing visual feature>."

---

## 2. Face

Prompt block: `CHARACTER` → `face`

| Field                  | Value | Status |
|------------------------|-------|--------|
| Head shape             | TBD | TBD |
| Face length vs width   | TBD | TBD |
| Jawline                | TBD | TBD |
| Chin                   | TBD | TBD |
| Cheekbones             | TBD | TBD |
| Cheek fullness         | TBD | TBD |
| Nose — bridge          | TBD | TBD |
| Nose — tip and width   | TBD | TBD |
| Ears — visible?        | TBD | TBD |
| Facial hair            | TBD | TBD |
| Distinguishing marks   | TBD | TBD |

Face proportions are the highest-value identity signal and the first thing to drift.
Numeric proportions (eye line, nose base, mouth line) are measured in `visual-spec.md` §3.

---

## 3. Eyes

Prompt block: `CHARACTER` → `eyes`

| Field              | Value | Status |
|--------------------|-------|--------|
| Eye shape          | TBD | TBD |
| Eye size in face   | TBD | TBD |
| Eye spacing        | TBD | TBD |
| Iris color         | TBD | TBD |
| Iris size          | TBD | TBD |
| Upper lid          | TBD | TBD |
| Lower lid          | TBD | TBD |
| Lashes             | TBD | TBD |
| Catchlight         | TBD | TBD |
| Default gaze       | At camera | PROPOSED |

Eyes carry expression first (`PROMPT_GUIDE.md` §5) and must stay pixel-stable across all
16 visemes (`ASSET_SPEC.md` §7). Both facts trace back to this section.

---

## 4. Eyebrows

Prompt block: `CHARACTER` → `eyebrows`

| Field           | Value | Status |
|-----------------|-------|--------|
| Shape           | TBD | TBD |
| Thickness       | TBD | TBD |
| Arch position   | TBD | TBD |
| Height above eye| TBD | TBD |
| Color           | TBD | TBD |
| Inner end       | TBD | TBD |
| Outer end       | TBD | TBD |

---

## 5. Hair

Prompt block: `CHARACTER` → `hair`

| Field           | Value | Status |
|-----------------|-------|--------|
| Cut             | TBD | TBD |
| Length          | TBD | TBD |
| Part            | TBD | TBD |
| Fringe / bangs  | TBD | TBD |
| Texture         | TBD | TBD |
| Volume          | TBD | TBD |
| Base color      | TBD | TBD |
| Highlight color | TBD | TBD |
| Hairline shape  | TBD | TBD |
| Silhouette      | TBD | TBD |

Hair silhouette is what a reviewer notices at 256px in a contact sheet. Describe the
outline, not just the color.

---

## 6. Skin

Prompt block: `CHARACTER` → `skin`

| Field             | Value | Status |
|-------------------|-------|--------|
| Base tone         | TBD | TBD |
| Undertone         | TBD | TBD |
| Shadow tone       | TBD | TBD |
| Blush / warmth    | TBD | TBD |
| Finish            | TBD | TBD |

Hex values are recorded in `visual-spec.md` §5.

---

## 7. Clothing

Prompt block: `CHARACTER` → `clothing`

| Field            | Value | Status |
|------------------|-------|--------|
| Garment          | TBD | TBD |
| Neckline         | TBD | TBD |
| Collar           | TBD | TBD |
| Sleeves          | TBD | TBD |
| Primary color    | TBD | TBD |
| Secondary color  | TBD | TBD |
| Pattern          | TBD | TBD |
| Fabric read      | TBD | TBD |
| Visible extent   | TBD | TBD |

Clothing is visible in every asset and is a frequent silent drift target — collar shape
and button count change between generations without anyone noticing until QC.

---

## 8. Accessories

Prompt block: `CHARACTER` → `accessories`

| Field       | Value | Status |
|-------------|-------|--------|
| Glasses     | TBD | TBD |
| Earrings    | TBD | TBD |
| Necklace    | TBD | TBD |
| Headwear    | TBD | TBD |
| Other       | TBD | TBD |

If the character has no accessories, write `none` explicitly in each field and state
`accessories: none` in the master prompt. An empty field is read as "unspecified" and
FLUX will invent something.

---

## 9. Art Style

Prompt block: `STYLE`

| Field              | Value | Status |
|--------------------|-------|--------|
| Style family       | TBD (2D illustration — `CLAUDE.md`) | TBD |
| Line work          | TBD | TBD |
| Line weight        | TBD | TBD |
| Line color         | TBD | TBD |
| Shading model      | TBD | TBD |
| Shadow edges       | TBD | TBD |
| Color treatment    | TBD | TBD |
| Texture / grain    | TBD | TBD |
| Level of detail    | TBD | TBD |
| Outline present?   | TBD | TBD |

Photorealistic drift is a named failure mode (`PROMPT_GUIDE.md` §8). The style
description is the defence, so it must be specific enough to be violated.

---

## 10. Lighting

Prompt block: `LIGHTING`

| Field              | Value | Status |
|--------------------|-------|--------|
| Key direction      | TBD | TBD |
| Key softness       | TBD | TBD |
| Key color          | TBD | TBD |
| Fill strength      | TBD | TBD |
| Fill direction     | TBD | TBD |
| Rim / back light   | TBD | TBD |
| Shadow side        | TBD | TBD |
| Contrast ratio     | TBD | TBD |
| Ambient occlusion  | TBD | TBD |

Lighting is held constant across the entire library so that expression, viseme, and pose
layers composite without a visible seam (`DECISIONS.md` → ADR-004).

---

## 11. Camera and Framing

Prompt block: `CAMERA`

| Field               | Value | Status |
|---------------------|-------|--------|
| Default camera class| `close-up` | PROPOSED |
| Head angle          | TBD | TBD |
| Head tilt           | TBD | TBD |
| Shoulder line       | TBD | TBD |
| Lens character      | TBD | TBD |
| Eye level vs camera | TBD | TBD |

Measured framing geometry — head height, eye line, mouth line, margins — lives in
`visual-spec.md` §3. This section holds only the descriptive form that reaches the prompt.

---

## 12. Personality

Prompt block: none — this section does not reach the prompt directly.

| Field              | Value | Status |
|--------------------|-------|--------|
| Core temperament   | Warm, calm, credible | PROPOSED |
| Energy level       | Moderate — engaged, not excitable | PROPOSED |
| Address to viewer  | Direct, friendly, non-condescending | PROPOSED |
| Humor              | Light, rare | PROPOSED |
| Expression default | `neutral` with a trace of warmth | PROPOSED |

Personality exists to keep the 12 expressions coherent as a set. It decides, for example,
whether `excited` reads as delighted or as manic — a judgement the expression prompts
inherit rather than re-litigate. Intensity defaults to **moderate**
(`PROMPT_GUIDE.md` §5); extremes read as caricature at close framing.

---

## 13. Narrator Role

Prompt block: none.

| Field              | Value | Status |
|--------------------|-------|--------|
| Content domain     | Thai-language narrated content | PROPOSED |
| Register           | Conversational-professional | PROPOSED |
| Relationship       | Explainer / guide | PROPOSED |
| Speaking style     | Steady pace, clear articulation | PROPOSED |
| On-screen function | Talking head + gesture support | PROPOSED |

Speaking style is the bridge to PHASE 7–10: articulation clarity sets how pronounced the
viseme set needs to be. It is recorded now and consumed later. No PHASE 7+ work follows
from writing it down (`DECISIONS.md` → ADR-001).

---

## 14. Immutable vs Variable

The contract that every derived asset is held to.

**Immutable** — never changes in any asset, in any phase:

- face proportions and head shape (§2)
- eye shape, eye color, eye position (§3)
- eyebrow shape and thickness (§4) — *position* varies with expression
- hairstyle, hair color, hair part (§5)
- skin tone (§6)
- clothing and accessories (§7, §8)
- art style and line style (§9)
- lighting direction and quality (§10)

**Variable by asset class:**

| Asset class | May change                                   | Must not change                    |
|-------------|----------------------------------------------|------------------------------------|
| Expression  | eyes (aperture), eyebrows (position), mouth corners, gaze | mouth shape beyond corners, head size, body |
| Viseme      | mouth and jaw only                            | everything else, including expression |
| Pose        | body, shoulders, arms, hands, camera class    | face, head geometry, identity      |

Anything changing outside its class's "may change" column is a FAILED asset
(`ASSET_SPEC.md` §10). Regenerate with a stronger preservation statement; do not accept it.

---

## 15. Known Drift Risks

Filled from QC observation as the library is generated. Each entry names the failure and
the prompt change that fixed it, so the fix is reusable rather than rediscovered.

| # | Region | Observed drift | Fix applied | Phase |
|---|--------|----------------|-------------|-------|
| — | — | *(none recorded yet)* | — | — |

This table is the source for targeted negative prompts (`PROMPT_GUIDE.md` §8). A negative
term is only added after a failure appears here.

---

## 16. Change Control

| Version | Date | Change | Assets invalidated |
|---------|------|--------|--------------------|
| v0.1    | 2026-08-25 | Structure created, awaiting reference image | none |

Rules:

- A change to any **immutable** field (§14) is a MAJOR version bump and invalidates every
  approved asset in `character/`.
- A wording refinement that does not change intended output is a MINOR bump.
- The bible version is recorded in the master prompt version, which is recorded in every
  asset's metadata (`ASSET_SPEC.md` §11). An asset must remain traceable to the bible
  version it was generated under.
