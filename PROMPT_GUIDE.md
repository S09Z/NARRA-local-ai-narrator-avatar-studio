# PROMPT_GUIDE.md

# NARRA — Prompt Architecture Guide

How prompts are structured, versioned, and constrained so that one character stays
one character across every generated asset.

Source of truth for the character itself: `character/bible/character-bible.md` (PHASE 1).
Prompt files live in `prompts/`.

---

## 1. Prompt Architecture

Every prompt is assembled from ordered blocks. Blocks are always emitted in this order
so that identity constraints precede task instructions.

```
CHARACTER      identity — who this is (from the character bible)
PRESERVATION   what must not change
TASK           the single change being requested
EXPRESSION     eyes, eyebrows, brow tension, gaze
VISEME         mouth shape only
POSE           body, shoulders, hands
CAMERA         framing, distance, angle
LIGHTING       key/fill, direction, softness
STYLE          art style, line style, rendering
OUTPUT         resolution, background, format constraints
```

Rules:
- A block that does not apply is omitted, not left empty.
- Exactly one TASK per generation. Two changes = two generations.
- Blocks are concrete and visual. "Beautiful", "high quality", "masterpiece", and
  "8k" carry no visual meaning for FLUX and are not used.
- Prompts describe the *result*, not the editing operation
  ("mouth closed, lips pressed together" — not "apply a mouth mask").

### Storage layout

```
prompts/master/        master-character-vN.N.md   canonical CHARACTER + STYLE + PRESERVATION
prompts/expressions/   <expression>-vN.N.md       EXPRESSION block per expression
prompts/visemes/       <viseme>-vN.N.md           VISEME block per viseme
prompts/poses/         <pose>-vN.N.md             POSE + CAMERA block per pose
```

### Versioning

- Files are versioned `vMAJOR.MINOR` in the filename: `master-character-v1.0.md`.
- MINOR: wording refinement that does not change intended output.
- MAJOR: any change that alters the character or the intended visual result.
- Approved assets record the exact prompt version used. Never edit a version in place
  after assets have been locked against it — publish a new version.

---

## 2. Master Prompt

The master prompt holds everything that is true of the character in every asset.
It is composed once and included verbatim by all derived prompts.

Skeleton (`prompts/master/master-character-v1.0.md`):

```
CHARACTER:
  <age range, build, role: Thai narrator>
  face: <face shape, proportions, distinguishing features>
  eyes: <shape, color, size, spacing>
  eyebrows: <shape, thickness, color>
  hair: <cut, length, part, color, texture>
  skin: <tone>
  clothing: <garment, cut, color, pattern>
  accessories: <or: none>

STYLE:
  <art style; line style; shading; color treatment>

LIGHTING:
  <key direction, softness, fill, background separation>

CAMERA:
  <default framing and lens character>

OUTPUT:
  1024x1024, square, <background specification>
```

The master prompt is descriptive only. It never contains a TASK.

---

## 3. Character Preservation Rules

The canonical reference image is authoritative. Preservation is stated explicitly in
the prompt, not assumed.

Always preserved unless the TASK names it:
- face proportions and head shape
- hairstyle, hair color, hair part
- eyes, eyebrows
- skin tone
- clothing and accessories
- art style, line style
- lighting direction and quality
- camera framing and head size in frame

Standard PRESERVATION block:

```
PRESERVATION:
  Keep the same person: identical <preserved features> as the reference image.
  Do not change anything except <TASK target>.
```

`<preserved features>` is **built, not pasted**. Pasting a fixed list contradicts itself
the moment the TASK targets one of the features it names — an expression edit would emit
"identical eyebrows … do not change anything except the eyebrows". So each prompt declares
which features its TASK touches, and those are removed from the list.

Feature keys: `face`, `eyes`, `eyebrows`, `nose`, `mouth`, `hair`, `skin`, `clothing`,
`accessories`, `style`, `lighting`, `camera`.

| Asset class | Touches                 |
|-------------|-------------------------|
| expression  | `eyes, eyebrows, mouth` |
| viseme      | `mouth`                 |
| pose        | `camera`                |

`scripts/generation/compile_prompt.py` generates the block, so the wording cannot drift
between assets. See `prompts/README.md` §3 and `DECISIONS.md` → ADR-010.

Preservation discipline:
1. The TASK names exactly one target region.
2. The PRESERVATION block names the untouched regions positively.
3. The NEGATIVE block forbids the drift modes seen in QC.
4. Anything that changed outside the TASK target is a FAILED asset — regenerate with a
   stronger preservation statement rather than accepting it.

---

## 4. Reference-Edit Rules

Reference editing is the default generation method (see `DECISIONS.md` → ADR-003).

```
reference image → region constraint → FLUX.2 Klein 4B Base → derived asset
```

Rules:
- Every derived asset edits `character/reference/master.png`, never another derived asset.
  Editing a derived asset compounds drift.
- Constrain the edit to the smallest region that can express the change:
  - viseme → mouth and jaw only
  - expression → eyes, eyebrows, and mouth corners
  - pose → body and arms, head region untouched where possible
- Denoise/edit strength is kept as low as the change allows. If a viseme needs a high
  edit strength to appear, the prompt is wrong, not the strength.
- The instruction is phrased as a change, singular and explicit:
  "Change only the mouth. The mouth is <shape>. Everything else is identical."
- Head position, head size, and mouth anchor must match the reference. See
  `ASSET_SPEC.md` → Mouth Anchor.

---

## 5. Expression Prompt Rules

An expression is carried by the eyes and eyebrows first, the mouth second.

- Describe muscle-level geometry, not emotion words alone.
  Weak: "happy". Strong: "eyes slightly narrowed, outer brows relaxed, cheeks raised,
  mouth corners lifted".
- Emotion words may appear as a summary line, but never as the only description.
- Expression prompts must not specify a viseme. Expression assets use the REST mouth
  unless the expression is defined by mouth shape (e.g. `surprised`).
- Gaze stays at camera unless the expression set explicitly defines otherwise
  (`thinking` may look up/aside — state it).
- Intensity is stated: subtle / moderate / strong. Narrator expressions default to
  moderate; extremes read as caricature at close framing.

Canonical set (PHASE 3): neutral, friendly, happy, excited, serious, concerned,
surprised, confused, thinking, explaining, proud, embarrassed.

---

## 6. Viseme Prompt Rules

A viseme is a mouth shape, nothing else. This is the strictest prompt class in the project.

Hard rules:
- TASK is always "change only the mouth".
- The expression, gaze, eyebrows, and head angle are held identical to REST.
- Describe: lip opening (height), lip spread (width), lip rounding, teeth visibility,
  tongue visibility, jaw drop.
- MBP must be visually distinct from REST — REST is a relaxed closed mouth; MBP is
  actively pressed lips. If a reviewer cannot distinguish them side by side, both fail.
- The mouth anchor (center X/Y) is identical across all 16 visemes.

Descriptor template:

```
VISEME <NAME>:
  jaw: <closed | slightly open | open | wide open>
  lips: <relaxed | pressed | rounded | spread | tucked>
  opening: <height descriptor>
  width: <narrow | neutral | wide>
  teeth: <hidden | upper visible | both visible>
  tongue: <hidden | tip visible against upper teeth>
```

Canonical set (PHASE 4): REST, A, I, U, E, O, AE, AO, MBP, FV, TH, KG, S, SH, L, N.
This is a visual animation approximation for Thai speech, not a complete phonological model.
Thai phoneme→viseme mapping is documented in `docs/thai-viseme/`.

---

## 7. Pose Prompt Rules

- Pose changes the body; the head and face follow the master prompt.
- State shoulder line, arm position, hand position, and torso rotation explicitly.
- Hands are the highest-failure region: prefer poses with hands fully in frame or fully
  out of frame. Partially cropped hands fail QC most often.
- CAMERA is part of the pose prompt: close-up, medium, upper-body, three-quarter.
- Framing must keep the head size consistent within each camera class so poses remain
  interchangeable at composition time.

---

## 8. Negative Prompt Strategy

FLUX responds primarily to the positive prompt. Negatives are a targeted correction
tool, not a quality incantation.

Principles:
- Never paste a generic "bad hands, worst quality, jpeg artifacts" block. It is noise.
- Add a negative term only after a specific failure has been observed in QC, and record
  which failure it addresses.
- Prefer fixing the positive prompt first. A negative that fights the positive prompt
  produces unstable output.
- Keep negatives short. Long negative prompts dilute every term in them.

Baseline negatives for this project:

```
NEGATIVE (identity):   different person, different face shape, different hairstyle,
                       different hair color, different clothing, aged face
NEGATIVE (framing):    changed camera distance, changed head size, cropped head, tilted head
NEGATIVE (viseme):     changed eyes, changed eyebrows, changed expression, moved mouth position
NEGATIVE (render):     photorealistic drift, style change, added text, watermark, extra limbs
```

Use only the group relevant to the asset class being generated.

Individual terms are filtered the same way the preserved list is: a prompt that
legitimately changes a feature does not also carry a negative forbidding it. A
"change only the hair" prompt drops `different hairstyle` and `different hair color`,
or it fights itself. Terms that guard a *property* rather than a *feature* are never
dropped — `moved mouth position` still applies to a viseme, whose mouth shape changes
but whose mouth position must not.

`pose` omits the framing group entirely, because a pose selects its camera class by
design. The compiler applies all of this; see `prompts/README.md` §3.

---

## 9. Prompt Compilation

The assembled prompt for a generation is:

```
master-character-vN.N
  + PRESERVATION (asset class)
  + TASK
  + <EXPRESSION | VISEME | POSE> block
  + CAMERA / LIGHTING overrides (if any)
  + OUTPUT
  + NEGATIVE (asset class)
```

Deterministic seed ranges (from `PLAN.md`):

| Asset class | Seed range   |
|-------------|--------------|
| Diagnostic  | 1000–1999    |
| Expression  | 10000–10999  |
| Viseme      | 20000–20999  |
| Pose        | 30000–30999  |

Diagnostic seeds cover gate tests (PHASE 1.4, PHASE 2.5) and never produce library
assets. See `DECISIONS.md` → ADR-009.

Every generation records its compiled prompt and prompt versions in
`metadata/generations/`. A locked asset must be re-creatable from its metadata alone.
