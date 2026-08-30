# DECISIONS.md

# NARRA — Architectural Decision Record

Durable architectural decisions with rationale and rejected alternatives.

Rules:
- One entry per decision. Append; do not rewrite history.
- A decision is only superseded by a newer dated entry that names it.
- Short-form status/context lives in `MEMORY.md`. Rationale lives here.

Entry format:

```
## ADR-NNN — Title
Date: YYYY-MM-DD
Status: proposed | accepted | superseded by ADR-NNN
Context:
Decision:
Rationale:
Alternatives rejected:
Impact:
```

---

## ADR-001 — Image generation before video/lip-sync
Date: 2026-08-24
Status: accepted

Context:
The end goal is a Thai narrator video pipeline (TTS → phoneme → viseme → animation → MP4).
Lip-sync animation is worthless if the underlying avatar frames drift in identity.

Decision:
The image-generation pipeline is built and production-locked (PHASE 6) before any
audio, phoneme, lip-sync, HyperFrames, or video work begins.

Rationale:
Character inconsistency is the dominant failure mode in generative avatar pipelines.
Discovering it after building an animation engine forces a full regeneration of every asset.
A hard phase gate makes the failure cheap and early.

Alternatives rejected:
- Build image and video pipelines in parallel — rejected: video work would be rebuilt
  on top of an unstable asset library.
- Prototype lip-sync with placeholder mouths — rejected: proves nothing about the real
  constraint (identity preservation under mouth edits).

Impact:
PHASES 7–10 are explicitly blocked. See `PLAN.md` → IMAGE PIPELINE GATE.

---

## ADR-002 — FLUX.2 Klein 4B as the default model family
Date: 2026-08-24
Status: accepted

Context:
Target hardware is a single NVIDIA RTX 5070 with 12GB VRAM and 32GB system RAM.

Decision:
- Default / iteration model: FLUX.2 Klein 4B Distilled
- Quality and reference-edit model: FLUX.2 Klein 4B Base
- FP8 weights where appropriate; batch size 1; 1024x1024 during iteration.

Rationale:
Klein 4B fits comfortably in 12GB without `--lowvram`, leaving headroom for the
text encoder and VAE. Keeping a fast/quality pair lets iteration stay cheap while
final approved assets get the stronger model.

Alternatives rejected:
- FLUX.2 Dev / 20GB+ class models — rejected: does not fit the target GPU; would make
  the project unusable on its own primary hardware.
- SDXL + IP-Adapter — rejected: weaker prompt adherence for structured multi-part
  prompts and weaker instruction-style reference editing.
- Cloud inference — rejected: the project is explicitly local-first.

Impact:
`models/` layout and all workflows assume the Klein 4B pair. Any model requiring
more than 12GB VRAM cannot become a default requirement.

---

## ADR-003 — Reference editing over full regeneration
Date: 2026-08-24
Status: accepted

Context:
Expressions and visemes are variations of one canonical character, differing in a
small region (mouth, eyes, eyebrows).

Decision:
Derive expression/viseme/pose assets by editing the canonical reference
(`character/reference/`) rather than re-generating from a text prompt.
Prompts must explicitly state what to preserve, e.g. "change only the mouth".

Rationale:
Text-to-image regeneration resamples the whole identity every time; seeds alone do not
hold a face stable across prompt changes. Localized editing keeps unrelated features
pixel-stable and makes the mouth anchor reusable.

Alternatives rejected:
- Fixed seed + text-to-image per asset — rejected: identity drifts when the prompt changes.
- Train a character LoRA first — rejected: expensive, needs a dataset that does not yet
  exist, and still drifts. LoRA remains an optional later optimization, not critical path.

Impact:
`workflows/reference-edit/` is the backbone workflow family. See `PROMPT_GUIDE.md`.

---

## ADR-004 — Expression and viseme are independent layers
Date: 2026-08-24
Status: accepted

Context:
12 expressions × 16 visemes = 192 combinations if generated exhaustively.

Decision:
Expression (eyes, eyebrows, head) and viseme (mouth) are generated and stored as
separate asset layers, composited at animation time.

Rationale:
Reduces the generation matrix from 192 assets to 28, and keeps QC tractable.
Composition is also what the later animation engine needs anyway — a mouth track
and an expression track running on independent timelines.

Alternatives rejected:
- Generate every expression×viseme combination — rejected: 192 assets to generate,
  QC, and re-generate on every prompt revision.
- Single blended prompt per frame — rejected: no reuse, non-deterministic, unaffordable.

Impact:
Requires a stable mouth anchor across all assets. See `ASSET_SPEC.md` → Mouth Anchor.

---

## ADR-005 — Native ComfyUI nodes; custom nodes require justification
Date: 2026-08-24
Status: accepted

Context:
Custom node packs are the primary source of breakage on ComfyUI upgrades.

Decision:
Required: ComfyUI + ComfyUI Manager only. Any additional node pack must be justified,
version-pinned, and recorded in `docs/operations/` before installation.

Rationale:
Reproducibility is a project requirement. Every unpinned custom node is an unversioned
dependency that can silently change generation output.

Alternatives rejected:
- Install the popular starter bundle (rgthree, KJNodes, Impact, WAS, etc.) up front —
  rejected: large untracked surface area for zero proven need.

Impact:
Adding a node pack is a documented change, not an incidental one.

---

## ADR-006 — Model weights and runtime media stay out of Git
Date: 2026-08-24
Status: accepted

Context:
FLUX checkpoints are multi-GB; iteration produces large volumes of throwaway images.

Decision:
`models/**` and `assets/generated/**` are ignored. Only explicitly approved character
assets (`character/**`, `assets/approved/**`) may be committed, and only on approval.
Git LFS is not used at this stage.

Rationale:
Keeps the repository clonable and reviewable. Approved assets are few, small, and are
genuine project artifacts; everything else is reproducible from seed + prompt + workflow.

Alternatives rejected:
- Git LFS for models — rejected: models are third-party downloads, reproducible from a
  documented source and hash; storing them adds cost with no reproducibility gain.
- Commit all generations for traceability — rejected: metadata records provenance
  (`metadata/generations/`) at a fraction of the size.

Impact:
Reproducibility depends on metadata discipline. See `ASSET_SPEC.md` → Metadata.

---

## ADR-007 — Documentation-first repository, no application framework
Date: 2026-08-24
Status: accepted

Context:
The project begins as a generation pipeline driven by ComfyUI workflows and prompts,
not as an application.

Decision:
The repository scaffolds documentation, prompts, workflows, assets, metadata, and
plain scripts. No web framework, package manager manifest, or CLI application is
created until PHASE 10 requires one.

Rationale:
Premature scaffolding creates maintenance surface that the current phases never exercise.
The artifacts that matter now are prompts, workflows, and validated images.

Alternatives rejected:
- Python package + Typer CLI up front — rejected: PHASE 10 concern; the CLI surface
  (`narra generate-*`) is not yet known.

Impact:
`scripts/` holds standalone utilities. A packaged CLI is a PHASE 10 decision.

---

## ADR-008 — Versioned reference master with a stable `master.png` alias
Date: 2026-08-25
Status: accepted

Context:
`PLAN.md` §1.1 and `PROMPT_GUIDE.md` §4 specify the canonical reference as
`character/reference/master.png`. `ASSET_SPEC.md` §5 requires every asset to carry a
versioned filename, `<character>-<type>-<name>-v<version>.png`. The two cannot both be
satisfied by a single file, and PHASE 1.1 has to write something.

Decision:
Keep both. `narra-reference-master-v1.png` is the real, versioned artifact and carries
the sidecar metadata. `master.png` is a byte-identical **copy** that workflows and
prompts may hardcode. `scripts/validation/validate_reference.py --check-imported`
enforces that the two are identical.

Rationale:
Version history is a project requirement — a reference bump invalidates the whole asset
library, so it must be visible in the filename. But ComfyUI workflow JSON hardcodes
image paths, and rewriting every workflow on a reference bump is exactly the kind of
churn that produces mixed-reference assets. The alias absorbs the version change in one
place. A copy rather than a symlink because ComfyUI must resolve the path identically on
Windows, Linux, and macOS, and Git symlink handling on Windows is a known failure mode.

Alternatives rejected:
- `master.png` only — rejected: no version history on the single most important asset;
  a replaced reference would be undetectable after the fact.
- Versioned file only — rejected: every reference bump becomes a rewrite of every
  workflow JSON, with silent partial-migration risk.
- Symlink instead of copy — rejected: unreliable across the platforms this project runs on.

Impact:
A ~1.5MB duplicate file in the repository, and one enforced invariant. The validator
fails if the copy drifts, so the duplication cannot silently become a second reference.

---

## ADR-009 — Diagnostic seed range 1000–1999
Date: 2026-08-25
Status: accepted

Context:
`PLAN.md` §2.4 assigns deterministic seed ranges to expressions (10000–10999), visemes
(20000–20999), and poses (30000–30999). The PHASE 1.4 baseline identity tests and the
PHASE 2.5 reference-edit tests also need fixed seeds, and have no assigned range.

Decision:
Diagnostic and gate-test generations use seeds **1000–1999**. PHASE 1.4 baseline tests
take 1001–1003. These seeds are never used for library assets.

Rationale:
Gate tests must be re-runnable with the same seed to tell a prompt change from sampling
noise. Sharing a range with library assets would make a diagnostic run and an approved
asset indistinguishable in `metadata/generations/`, which breaks the rule that an
approved asset is reproducible and identifiable from its metadata alone.

Alternatives rejected:
- Random seeds for diagnostics — rejected: a failed gate test could not be reproduced,
  which is when reproducibility matters most.
- Reuse the expression range — rejected: pollutes the library's seed space and makes
  provenance ambiguous.

Impact:
`PROMPT_GUIDE.md` §9's seed table gains a fourth row. Diagnostic outputs live in
`assets/generated/` and are never promoted to `character/`.

---

## ADR-010 — Preservation and negative terms are generated, not pasted
Date: 2026-08-25
Status: accepted

Context:
`PROMPT_GUIDE.md` §3 specified the PRESERVATION block as a fixed sentence naming every
preserved feature, and §8 specified fixed negative groups. Implementing PHASE 2.1–2.4
showed both are self-contradictory the moment a TASK targets a feature they name. An
expression prompt would emit "identical eyebrows … do not change anything except the
eyebrows", and the PHASE 2.5 "change only the hair" test would carry "different
hairstyle" as a negative while asking for a different hairstyle.

Decision:
Each prompt declares a `touches` list of feature keys. `scripts/generation/compile_prompt.py`
builds the PRESERVATION block from the full feature list minus `touches`, and filters
individual negative terms by the same list. Negative terms that guard a property rather
than a feature are tagged and never dropped — `moved mouth position` still applies to a
viseme. `touches` defaults per asset class (expression: eyes, eyebrows, mouth; viseme:
mouth; pose: camera) so ordinary prompts never set it; diagnostics must declare it.

Rationale:
A prompt that contradicts itself produces unstable output, and the instability is
attributed to the model rather than to the prompt. Generating the block also means the
preservation wording is identical across all 38 library assets by construction, which is
the property that makes drift attributable to the TASK.

Alternatives rejected:
- Hand-write PRESERVATION per asset — rejected: 38 chances for the wording to drift, and
  drift in the preservation block is indistinguishable from drift in the model.
- Keep the fixed template and accept the contradiction — rejected: it is exactly the
  "negative that fights the positive prompt" failure `PROMPT_GUIDE.md` §8 warns about.
- Drop the contradicting terms manually at generation time — rejected: not reproducible
  from the prompt file, so the recorded metadata would not regenerate the asset.

Impact:
`PROMPT_GUIDE.md` §3 and §8 updated to describe the generated form. Prompt files gain an
optional `touches` header. Enforced by `compile_prompt.py --lint`.
