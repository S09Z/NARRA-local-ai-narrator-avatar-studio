# prompts/ — Prompt Sources

Versioned prompt sources for every generated asset. Rules and rationale live in
`PROMPT_GUIDE.md`; this file specifies the **file format and the compilation contract**
that `scripts/generation/compile_prompt.py` implements.

---

## 1. Layout

```
prompts/master/        master-character-vN.N.md   CHARACTER + STYLE + LIGHTING + CAMERA + OUTPUT
prompts/expressions/   <expression>-vN.N.md       TASK + EXPRESSION
prompts/visemes/       <viseme>-vN.N.md           TASK + VISEME
prompts/poses/         <pose>-vN.N.md             TASK + POSE + CAMERA
prompts/diagnostic/    <test>-vN.N.md             gate tests; never produce library assets
```

One file per asset. The master file is included verbatim by every compilation, which is
what makes one character stay one character (`PROMPT_GUIDE.md` §2).

---

## 2. File format

A prompt file is Markdown with a `---` delimited header and `## BLOCK` sections.
Deliberately parseable with the standard library — no YAML dependency
(`DECISIONS.md` → ADR-007).

```markdown
---
id: mbp
version: 1.0
kind: viseme
asset_name: MBP
task_target: the mouth and jaw
---

## TASK

Change only the mouth and jaw. Everything else is identical.

## VISEME

jaw: closed
lips: actively pressed together
opening: none
width: neutral
teeth: hidden
tongue: hidden
```

### Header fields

| Field         | Required for       | Meaning                                              |
|---------------|--------------------|------------------------------------------------------|
| `id`          | all                | Filename stem without the version suffix              |
| `version`     | all                | `MAJOR.MINOR`, matches the filename (`PROMPT_GUIDE.md` §1) |
| `kind`        | all                | `master`, `expression`, `viseme`, `pose`, `diagnostic`|
| `asset_name`  | non-master         | Canonical asset name — `MBP`, `happy`, `pointing-left`|
| `task_target` | non-master         | The one region the TASK may change; fills the PRESERVATION template |
| `camera_class`| pose               | `close-up`, `medium`, `upper-body`, `three-quarter`   |
| `seed`        | diagnostic         | Explicit seed; other kinds derive it (§4)             |
| `touches`     | diagnostic         | Comma-separated features the TASK may change (§3)     |
| `preservation`| optional           | `auto` (default) or `manual` to supply your own block |

### Block names

Only the ten block names in `PROMPT_GUIDE.md` §1 are valid: `CHARACTER`, `PRESERVATION`,
`TASK`, `EXPRESSION`, `VISEME`, `POSE`, `CAMERA`, `LIGHTING`, `STYLE`, `OUTPUT`.
An unknown block name is an error, not a warning — a typo'd block would otherwise be
silently dropped from every asset generated with it.

---

## 3. Compilation

```bash
# compile one asset
python3 scripts/generation/compile_prompt.py visemes/mbp-v1.0.md

# emit the metadata record instead of prompt text
python3 scripts/generation/compile_prompt.py visemes/mbp-v1.0.md --json

# lint every prompt file without compiling
python3 scripts/generation/compile_prompt.py --lint
```

Blocks are emitted in the fixed `PROMPT_GUIDE.md` §1 order regardless of the order they
appear in the files, so identity constraints always precede task instructions:

```
CHARACTER  PRESERVATION  TASK  EXPRESSION  VISEME  POSE  CAMERA  LIGHTING  STYLE  OUTPUT
```

Master blocks and asset blocks are merged; where both define a block, the **asset file
wins** (a pose overrides the master `CAMERA`). Blocks that end up empty are omitted, never
emitted blank.

### `touches` — which features leave the preserved list

The `PROMPT_GUIDE.md` §3 preservation block is a fixed sentence naming every preserved
feature. Pasted literally it contradicts itself as soon as the TASK targets one of those
features — an expression edit emits *"identical eyebrows … do not change anything except
the eyebrows"*. So the preserved list is **built**, not pasted: `touches` names the
features the TASK may change, and those are removed from the list.

Feature keys: `face`, `eyes`, `eyebrows`, `nose`, `mouth`, `hair`, `skin`, `clothing`,
`accessories`, `style`, `lighting`, `camera`.

Defaults by kind, so ordinary asset prompts never set it:

| Kind       | `touches`                | Rationale                                    |
|------------|--------------------------|----------------------------------------------|
| expression | `eyes, eyebrows`         | expression is carried by the eyes and brows first (`PROMPT_GUIDE.md` §5), and 9 of the 12 keep a REST mouth so visemes composite (`ASSET_SPEC.md` §6) |
| viseme     | `mouth`                  | a viseme is a mouth shape, nothing else (§6)  |
| pose       | `camera`                 | a pose selects its camera class (§7)          |
| diagnostic | *(required, no default)* | proving containment is the point of the test  |

The three expressions `ASSET_SPEC.md` §6 defines as open-mouthed — `excited`,
`surprised`, `explaining` — declare `touches: eyes, eyebrows, mouth` explicitly. No
expression touches `camera`: an expression that tilts the head moves the mouth anchor
with it (`DECISIONS.md` → ADR-012).

Set `preservation: manual` and supply a `## PRESERVATION` block only when a specific
observed drift mode needs stronger wording; the reason belongs in
`character-bible.md` §15.

### NEGATIVE

Assembled from the `PROMPT_GUIDE.md` §8 groups by asset kind. Only the relevant groups
are used — negatives are a targeted correction tool, not a quality incantation.

| Kind       | Negative groups                       |
|------------|---------------------------------------|
| expression | identity, framing, render             |
| viseme     | identity, framing, viseme, render     |
| pose       | identity, render                      |
| diagnostic | identity, framing, render             |

`pose` deliberately omits the framing group: a pose changes camera class by design, so
`changed camera distance` would fight its own positive prompt.

Individual negative terms are filtered by `touches` for the same reason the preserved
list is. A "change only the hair" prompt does not also carry `different hairstyle` as a
negative. Terms that guard a property rather than a feature are never dropped:
`moved mouth position` still applies to a viseme, whose mouth *shape* changes but whose
mouth *position* must not.

---

## 4. Deterministic seeds

Seeds are **derived, not chosen** — `seed = range_base + index in the canonical set`.

| Kind        | Base   | Range        | Canonical set                    |
|-------------|--------|--------------|----------------------------------|
| diagnostic  | 1000   | 1000–1999    | explicit `seed:` in the header   |
| expression  | 10000  | 10000–10999  | `ASSET_SPEC.md` §6 — 12 entries  |
| viseme      | 20000  | 20000–20999  | `ASSET_SPEC.md` §7 — 16 entries  |
| pose        | 30000  | 30000–30999  | `ASSET_SPEC.md` §8 — 10 entries  |

Derivation rather than hand-assignment means a seed is re-derivable from the asset name
alone, collisions are impossible within a set, and a reviewer can verify a recorded seed
by counting. An asset name outside its canonical set is an error — that is how a typo in
`asset_name` gets caught before it reaches metadata.

Ranges are set by `PLAN.md` §2.4 and `DECISIONS.md` → ADR-009.

---

## 5. Versioning

- Filenames carry the version: `mbp-v1.0.md`. The header `version` must agree with it.
- **MINOR** — wording refinement that does not change the intended output.
- **MAJOR** — any change to the character or the intended visual result.
- Never edit a version in place once assets are locked against it. Publish a new file.
- Every generation records `prompt.master_version` and `prompt.asset_prompt_version`
  (`ASSET_SPEC.md` §11), so an approved asset stays traceable to exact prompt text.

Because the master prompt is included in every compilation, a MAJOR bump of the master
invalidates every approved asset. It is a reference-level change, not a prompt tweak.

---

## 6. Lint rules

`--lint` enforces what `PROMPT_GUIDE.md` states as rules, so they fail at author time
rather than after 16 generations:

| Rule | Source |
|------|--------|
| Header `version` matches the filename | §1 |
| Only known block names | §1 |
| No empty blocks | §1 |
| Exactly one TASK per non-master file; master has none | §1, §2 |
| No filler words — `beautiful`, `high quality`, `best quality`, `masterpiece`, `award winning`, `ultra detailed`, `highly detailed`, `intricate details`, `8k`, `4k` | §1 |
| No editing-operation language — `inpaint`, `img2img`, `denoise`, `latent`, `cfg scale`, `apply a mask`; describe the result | §1 |
| `touches` names only known feature keys, and leaves something preserved | §3 |
| Expression files carry no VISEME block | §5 |
| Viseme files carry no EXPRESSION block | §6 |
| `asset_name` is in the canonical set for its kind | §9 |
| Pose files declare a valid `camera_class` | §7 |

The filler-word rule is the one that matters most in practice: those terms carry no visual
meaning for FLUX and dilute every other term in the prompt.
