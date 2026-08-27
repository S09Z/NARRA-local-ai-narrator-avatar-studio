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

---

## ADR-011 — Shared helper modules under `scripts/lib/`
Date: 2026-08-25
Status: accepted

Context:
PHASE 3.4 needs a second validator (`validate_asset.py`) that repeats the ASSET_SPEC §1–4
image checks already in `validate_reference.py`, and needs the canonical asset sets and
seed derivation already in `compile_prompt.py`. ADR-007 rules out a package or a manifest.

Decision:
Shared logic lives in plain modules under `scripts/lib/` — `canon.py` (canonical sets,
seed derivation, filename convention) and `imagecheck.py` (ASSET_SPEC §1–4 checks,
reporting, hashing). Scripts import them with an explicit two-line `sys.path` insert.
`validate_reference.py` and `compile_prompt.py` were migrated onto them in the same change.

Rationale:
Two copies of the canonical viseme set is not a style problem, it is a correctness one:
a compiler and a validator that disagree about the set would let an asset pass QC that
the compiler could never have produced. The same applies to the alpha and resolution
rules — updating one validator and not the other silently weakens the gate. The
`sys.path` insert is deliberately visible rather than hidden behind packaging, which
would be the manifest ADR-007 rejects.

Alternatives rejected:
- Duplicate the logic in each script — rejected: the duplicated content is precisely the
  spec, and a spec with two copies has no source of truth.
- Make `scripts/` a Python package with `__init__.py` and relative imports — rejected:
  requires running scripts as `-m` modules, which is a worse operator experience for
  standalone utilities.
- Add a `pyproject.toml` and install the project — rejected: ADR-007, PHASE 10 concern.

Impact:
`scripts/lib/` is not a CLI directory; nothing in it is executable. Tests import from it
directly. Adding a script that re-implements a check already in `imagecheck.py` should
be treated as a review failure.

---

## ADR-012 — Expression assets hold head angle, chin, and mouth fixed
Date: 2026-08-25
Status: accepted

Context:
`ASSET_SPEC.md` §6 describes `confused` as "asymmetric brows, slight head tilt" and
`proud` as "lifted chin, relaxed confident brows". ADR-004 makes expression and viseme
independent layers composited at animation time, which requires the mouth anchor and head
geometry to be identical across every asset. `ASSET_SPEC.md` §9 caps head vertical drift
at 1% of image height and anchor drift at 0.5% of image width.

Decision:
Expression assets do not tilt the head or lift the chin. `confused` is carried by brow
asymmetry alone; `proud` by relaxed brows and lowered lids. Expression prompts touch only
the eyes and eyebrows by default, leaving the mouth in the preserved list; the three
expressions `ASSET_SPEC.md` §6 defines as open-mouthed (`excited`, `surprised`,
`explaining`) declare `touches: eyes, eyebrows, mouth` explicitly. `ASSET_SPEC.md` §6 is
amended to match.

Rationale:
A head tilt or chin lift moves the mouth in frame. Any viseme composited onto that asset
lands in the wrong place, and the asset fails the §9 tolerance regardless of how good the
expression reads. Head movement is a pose-layer and animation-layer concern, where it can
be applied as a transform to a composited frame rather than baked into a still that then
cannot be reused. Keeping the mouth preserved by default also makes the nine REST-mouth
expressions checkable: the compiler emits "mouth shape and position" in their
PRESERVATION block, and QC can verify all nine share one mouth.

Alternatives rejected:
- Keep the tilt and widen the §9 tolerance — rejected: the tolerance is what makes the
  viseme layer work at all; widening it to fit one expression breaks all sixteen.
- Keep the tilt and exclude `confused` from compositing — rejected: a special-case asset
  that behaves unlike the other eleven is a permanent trap for the animation engine.
- Apply the tilt as a render-time transform now — rejected: PHASE 8/9 concern, blocked by
  ADR-001.

Impact:
`ASSET_SPEC.md` §6 rows for `confused` and `proud` updated. `confused` is now the hardest
expression in the set to make legible, since it has only brow asymmetry to work with — if
it fails the 256px legibility check, the fix is stronger asymmetry, not a head tilt.

---

## ADR-013 — The permitted edit region is recorded, and containment is machine-checked
Date: 2026-08-25
Status: accepted

Context:
"Change only the mouth" is the strictest rule in the project (`PROMPT_GUIDE.md` §6) and,
through PHASE 3, was only checkable by eye. A viseme that quietly moved an eyebrow would
pass every automated check, and the failure would surface in PHASE 8 as lip-sync that
looks subtly wrong across the whole library.

Decision:
`character/bible/mouth-anchor.json` records an `edit_region` alongside the anchor — the
normalized box the reference-edit workflow is permitted to touch. `validate_asset.py`
diffs a viseme against the reference and fails the asset if any changed pixel falls
outside that box, reporting the overshoot per side in pixels.
`scripts/utilities/measure_anchor.py` writes both, deriving the region from the measured
mouth box unless one is given explicitly.

Rationale:
The diff is the only direct evidence of what an edit actually changed. Prompt wording,
denoise strength, and mask geometry are all proxies; the changed-pixel bounding box is the
thing itself. Recording the region rather than inferring it from the anchor also means the
QC region and the workflow's mask are the same number, so a mask that is too tall fails QC
instead of silently permitting eye drift.

The region is derived asymmetrically — much taller below the anchor than above — because a
viseme opens the jaw downward. `A` is the maximum jaw drop in the set; a symmetric box
either clips it or reaches the eyes.

Alternatives rejected:
- Infer the permitted region from the anchor at validation time — rejected: the validator
  and the workflow would then hold independent opinions about the mask, and the
  disagreement would be invisible.
- Check the changed-region *centre* instead of its bounds — rejected: an edit that moves
  an eyebrow and the mouth has a centre between them that can still land inside the mouth
  region. Bounds catch it; a centre does not.
- Per-asset manual review only — rejected: sixteen assets, and the failure is a few pixels
  in a region nobody is looking at.

Impact:
The check reports SKIP until the anchor is measured in PHASE 4.3, which needs the
reference image. It applies to visemes only; expression containment would need the eye and
brow landmarks in `visual-spec.md` §3, which are also unmeasured.

---

## ADR-014 — Camera classes are specified as a ratio to the close-up head height
Date: 2026-08-25
Status: accepted

Context:
`PLAN.md` §5.2 requires four camera classes, and `ASSET_SPEC.md` §8 requires head size to
be consistent within a class. Head height can only be measured from the approved
reference, which does not exist yet — but the pose prompts and the framing rules have to
be written now, and they need the classes to mean something.

Decision:
Each class is specified by its **ratio to the `close-up` head height** — `medium` 0.71,
`upper-body` 0.60, `three-quarter` 0.48 — together with a crop line and a hands rule.
Absolute targets are recorded as derived estimates and are replaced by
`close-up × ratio` once `close-up` is measured. Tolerance within a class is 2% of image
height.

Rationale:
The ratio is the part that is actually a decision; the absolute is a measurement. Writing
the ratio down now makes the classes definable before the reference exists, and makes them
verifiable afterwards without re-deriving anything. It also makes an out-of-tolerance pose
diagnosable: if `upper-body` assets disagree with each other, the class is broken, and if
they agree with each other but not with `0.60 × close-up`, the estimate was wrong.

The estimates come from standard figure proportions — roughly 7.5 heads tall, ~0.25 head
of headroom, crop lines at ~2.2 / 3.2 / 3.8 / 4.8 heads from the crown. They are stated as
estimates in `visual-spec.md` §2 rather than presented as measurements.

Alternatives rejected:
- Leave head height entirely `TBD` until the reference exists — rejected: the pose prompts
  would have no framing definition to write against, and four classes that mean nothing
  are worse than four estimates that can be corrected.
- Specify absolute pixel heights now — rejected: they would be fiction, and fiction in a
  spec file is indistinguishable from a measurement six weeks later.
- Define classes by crop line alone — rejected: two poses can share a crop line and still
  differ in head size if the camera distance changed, which is exactly the drift §8 exists
  to prevent.

Impact:
`visual-spec.md` §2 carries both columns; only the ratio is binding. The `close-up`
measurement is now a dependency of PHASE 5 QC as well as PHASE 4.3.

---

## ADR-015 — Narrator compositions are validated data, and open-mouth expressions cannot host a viseme track
Date: 2026-08-25
Status: accepted

Context:
`PLAN.md` §5.3 asks for five reusable narrator states. ADR-004 makes expression and viseme
independent layers composited at animation time, and `ASSET_SPEC.md` §6 defines three
expressions — `excited`, `surprised`, `explaining` — as carrying an open mouth.

Decision:
The five states live in `character/compositions/narrator-states.json` as recipes over the
layers (pose + camera class + expression + mouth mode), validated by
`scripts/validation/validate_compositions.py`. A state whose mouth is `viseme-track` must
use a REST-mouth expression; the validator fails any state that composites a viseme track
over an open-mouth expression. States built on open-mouth expressions declare
`mouth: static` and are non-speaking beats.

Rationale:
The constraint is a direct consequence of ADR-004 and was not previously written down
anywhere: an open-mouth expression has already spent its mouth, so compositing a viseme
over it renders two mouths. Discovering that in PHASE 8, after the animation engine is
built around a state table, is exactly the class of failure ADR-001's phase gate exists to
prevent.

Encoding the states as data rather than prose means the layer combinations are checked
against the canonical sets now — a state naming a pose that will never be generated fails
today. It also gives PHASE 8 something to consume directly instead of re-deriving the
table from a document.

The visible consequence: the `explaining` *state* uses the `friendly` expression, not the
`explaining` one. That looks like an inconsistency until the rule is understood, so the
state records the reason inline.

Alternatives rejected:
- States as a prose section in a runbook — rejected: nothing would check that the poses and
  expressions they name are canonical, and PHASE 8 would re-key the table by hand.
- Allow a viseme track over open-mouth expressions and blend — rejected: blending two
  mouths is a compositing problem invented to avoid a spec decision, and it would need
  per-pair tuning across 3 × 16 combinations.
- Generate closed-mouth variants of the three open-mouth expressions — rejected: 15
  expressions instead of 12, for states that are deliberately non-speaking beats.

Impact:
Five states validated. `NARRATOR_STATES`, `MOUTH_MODES`, and `OPEN_MOUTH_EXPRESSIONS` live
in `scripts/lib/canon.py` as the single source of truth.

---

## ADR-016 — The PHASE 6 gate reads recorded sign-offs, and the baseline is generated
Date: 2026-08-25
Status: accepted

Context:
`PLAN.md` §6 is the hard gate before video: 12 expressions, 16 visemes, 10 poses,
contact sheets, a resolution lock, a metadata lock, and a production baseline. Through
PHASE 5 those requirements were checkable only in pieces — `validate_asset.py` judged one
asset, `--set` counted one set, and whether a person had actually reviewed an asset lived
nowhere at all. "PHASE 6 passed" was a claim, not a record.

Decision:
`scripts/validation/lock_library.py` runs the whole gate in one place and, on success,
writes `metadata/production-lock.json` — every locked asset with its sha256, seed, model,
workflow, and prompt version. `validate_asset.py --approve "name"` records the human half
of `ASSET_SPEC.md` §10 into `metadata/validation/`, and the gate refuses any asset whose
record is not `approved`. Writing the lock is also what mirrors each sidecar into
`metadata/generations/` (§11) and what generates `docs/production-baseline.md` (§6.5).
`--verify` re-checks the files against the lock.

Rationale:
The two halves of QC fail differently. The machine half is cheap and should be re-run
constantly; the human half is expensive and is worth recording once. Keeping the sign-off
in a file is what makes the gate mean anything — otherwise the only evidence that anyone
looked at the 38 assets is that someone said so.

Generating the baseline instead of writing it by hand follows from the same reasoning. A
hand-maintained baseline is accurate exactly until the first regenerated asset, and its
inaccuracy is invisible. Derived from the sidecars, it cannot describe a library that does
not exist, and `--verify` turns a silently edited asset into a failure.

Alternatives rejected:
- A checklist in a runbook: unenforceable, and the failure mode is a forgotten tick.
- Trusting `validation.status: approved` in the asset's own sidecar: the sidecar is written
  by the generator, so approval would be self-certified by the thing under review.
- Locking by git tag alone: a tag records that a commit happened, not that 38 specific
  images each passed 20 checks and were signed for.

Impact:
PHASE 7 is unblocked by `lock_library.py` exiting 0, and by nothing else. Regenerating a
locked asset invalidates the lock; re-run the gate and re-lock. `docs/production-baseline.md`
is a generated file and is not edited by hand.

---

## ADR-017 — Upscales are derivatives, kept outside the library
Date: 2026-08-25
Status: accepted

Context:
`ASSET_SPEC.md` §1 allows an optional 2048x2048 upscale of approved assets after the
PHASE 6 lock, but said nothing about where such a file lives, what it is called, or how it
is traced back to the master it came from.

Decision:
An upscale lives in `assets/approved/upscaled/`, is named `<master-stem>-up2048.png`, and
carries a sidecar recording `derived_from`, `derived_from_sha256`, `resolution`, and
`upscaler`. It is never an input to a further edit. The gate fails any upscale whose
`derived_from_sha256` does not match the master currently in the lock.

Rationale:
The library is the set of assets everything else is derived from, and it is 1024x1024 by
§1. A 2048 file sitting in `character/` would eventually be picked up as a reference edit
input, and the resulting asset would be reproducible only from a file that is itself a
derivative — two generations away from the recorded workflow.

Pinning the master's sha256 is what makes the derivative honest. An upscale whose master
has since been regenerated is a picture of a character that no longer exists in the
library, and without the hash nothing would ever say so.

Alternatives rejected:
- `character/<type>/` with a `-2048` suffix: closer to hand, and that is the problem.
- No rule until upscaling is actually needed: the check costs nothing while the directory
  is empty, and writing it afterwards means writing it after the first mistake.

Impact:
`scripts/validation/lock_library.py` reports SKIP while no upscales exist, and enforces the
rule as soon as one does. Upscales are recorded in the lock under `upscales`.

---

## ADR-018 — Head drift is measured within a camera class, not against the reference
Date: 2026-08-25
Status: accepted

Context:
`ASSET_SPEC.md` §9 caps head vertical drift at 1% of image height, and `validate_asset.py`
implemented that by comparing every asset's silhouette against the close-up reference.
Every pose in the library is `medium` or wider (`docs/workflows/pose-generation.md` §2), so
the check was measuring the camera move rather than a defect: all 10 poses would have
failed the PHASE 6 gate, correctly by the letter of the check and wrongly in fact.

Decision:
Drift against the reference applies to close-up assets — the reference, expressions, and
visemes. For an asset that records a wider `camera_class`, `validate_asset.py` reports the
reference comparison as SKIP and requires only that a `mouth_anchor` is recorded, and
`lock_library.py` instead compares silhouette crown positions *within* each camera class
against the same 1% tolerance.

Rationale:
§2 and §8 already say what consistency means for poses: within a camera class, not across
them. Comparing a three-quarter shot to a close-up asks the wrong question. What has to
hold is that two `medium` poses can be intercut, and crown position is the part of that a
script can measure from an alpha channel.

Head *height* — crown to chin — is the value `visual-spec.md` §2 specifies per class, and
it cannot be measured from alpha alone because nothing in the silhouette separates head
from body. It stays in the human checklist rather than being approximated.

Alternatives rejected:
- Per-class reference images: four references, four things to keep consistent, and the
  character identity contract in ADR-003 splits four ways.
- Widening the §9 tolerance until poses pass: that would also stop catching real drift in
  the 28 close-up assets, where the tolerance is doing its job.
- Face detection to measure true head height: a model dependency, on the QC path, to
  replace a check a person makes in a second from a contact sheet.

Impact:
`ASSET_SPEC.md` §9's tolerance is unchanged; where it is applied is now explicit. Poses
without a recorded `camera_class` still fail §8 in `validate_asset.py`.

---

## ADR-019 — The viseme mapping is prose and data, checked against each other
Date: 2026-08-27
Status: accepted

Context:
`docs/thai-viseme/thai-viseme-mapping.md` (PHASE 4.2) is a markdown table with the
reasoning attached — which phonemes look alike from the front, why `TH` is near-dead in
Thai, which rows a native speaker is most likely to correct. PHASE 7.3 needs the same
mapping as something a program can index into. Parsing the markdown at runtime would make
a prose edit able to break the pipeline; keeping only JSON would leave the reasoning
nowhere, and the reasoning is the part a Thai speaker reviews.

Decision:
Both. `thai-viseme-map.json` is what `scripts/lib/viseme_map.py` reads.
`thai-viseme-mapping.md` stays the prose and the review surface. `tests/audio/
test_viseme_map.py` parses the markdown tables and asserts every row matches the JSON, in
both directions.

Rationale:
Two copies of a mapping drift the moment one is edited. That is the same failure ADR-011
addressed for the canonical sets, and it is worse here: the markdown is what gets
reviewed, so a JSON that has drifted from it is a mapping nobody has actually approved.
A test is cheaper than either a runtime markdown parser or a lost rationale.

Alternatives rejected:
- Parse the markdown at runtime: a table-formatting change would become a pipeline
  outage, and the prose could no longer be edited freely.
- JSON only, prose deleted: throws away the ⚠ markers that tell a reviewer where to look.
- Generate the markdown from the JSON: the interesting content is the reasoning, which
  cannot be generated from a lookup table.

Impact:
Edit both files or neither. The `reviewed_by_thai_speaker` flag lives in the JSON, is
copied into every timeline, and is surfaced as a WARN on every validation run until it
becomes true.

---

## ADR-020 — G2P exceptions live in a lexicon, not in the rules
Date: 2026-08-27
Status: accepted

Context:
Thai spelling underdetermines pronunciation. A consonant between two vowels can be the
coda of one syllable or the onset of the next and both readings are legal — ดีครับ is
/diː.kʰrap/, not /diːk.rap/, and nothing in the orthography says so. Scoring the whole
segmentation fixes the common cases; loanwords, irregular readings, and compounds that
resyllabify need a dictionary the repository does not have.

Decision:
`scripts/lib/thai_g2p.py` scores candidate segmentations and penalises the readings that
are usually wrong. Where that still fails, `docs/audio/thai-lexicon.json` maps a surface
form to explicit IPA syllables and outranks any rule reading. The shipped file has 20
entries seeded from errors found while building PHASE 7.

Rationale:
Every fix that goes into the rules to repair one word risks breaking another, and the
damage is invisible without a corpus. A lexicon entry is scoped to exactly one word, is
data rather than code, and can be added by anyone who notices a mistake — no Python, no
test archaeology. It is also the natural upgrade path: a pythainlp dictionary can
populate it later.

Alternatives rejected:
- Special-case the rules per word: unbounded interaction between fixes.
- Require pythainlp: violates ADR-007, and makes the pipeline unrunnable on a machine
  that cannot install it.
- Accept the errors: a wrong parse becomes numbers in a JSON file and is invisible from
  then on.

Impact:
`build_timeline.py --report` is the intended way to find lexicon candidates, and the
runbook says so. Coverage and unparsed characters are recorded in every timeline;
below 95% coverage the build exits non-zero.

---

## ADR-021 — TTS and G2P engines are adapters, not dependencies
Date: 2026-08-27
Status: accepted

Context:
PLAN 7.1 asks for a Thai TTS engine and 7.2 for a phoneme approach, without naming
either. The right answer differs by machine: the production target is an RTX 5070 box
that does not exist yet, while the work is being done on a Mac. ADR-007 rules out a
package manifest, so a hard dependency on any engine is not available anyway.

Decision:
Both are registries. `tts.py` ships `say` (macOS, Thai voice Kanya, verified
byte-deterministic) as the development engine and `silence` (a silent WAV of the
estimated length) so tests and CI run anywhere. `thai_g2p.phonemize()` takes an engine
name and defaults to the built-in parser. Selecting the production TTS engine is
deferred to when the target machine exists; the criteria are recorded in
`docs/audio/phase-7-audio-pipeline.md` §2.

Rationale:
Choosing an engine now would be choosing it on the wrong hardware, and the choice is not
reversible for free — it decides whether a forced aligner is needed at all, since an
engine that emits its own phoneme timings upgrades `timing_source` from `fitted` to
`aligned` with no extra dependency. Every timeline records which engine made its audio,
so the decision stays visible in the artefacts rather than only in a document.

Alternatives rejected:
- Pick a neural TTS now: unverifiable on this machine, and it would share 12GB of VRAM
  with FLUX.
- Cloud TTS: CLAUDE.md is local-first throughout; this would be the first exception.
- No TTS until PHASE 6 passes: leaves 7.4 untestable against real audio, when a real
  Thai voice was available at zero cost.

Impact:
`silence` is not speech and must never be mistaken for it — it is labelled in the
metadata it writes. macOS `say` is a development engine and is not the production
answer.

---

## ADR-022 — A timeline records how its times were made
Date: 2026-08-27
Status: accepted

Context:
PHASE 7 can produce times three ways: a duration model with no audio at all, the same
model scaled so its total matches a measured WAV, or a real forced alignment. The three
are not equally trustworthy, and they are indistinguishable once written as numbers.
PHASE 8 will consume them without knowing which happened.

Decision:
Every timeline carries `timing_source` — `estimated`, `fitted`, or `aligned` — plus the
duration model version, the scale factor applied, the G2P coverage, and a `digest` over
the events and inputs that excludes the timestamp. Nothing writes `aligned` yet; the
value exists so the distinction cannot be lost later. `validate_timeline.py` warns on
`estimated`.

Rationale:
This is the same rule the image pipeline already lives by: an asset records the seed,
model, and prompt that produced it, and an unrecorded review is indistinguishable from
no review (ADR-016). A guessed time that looks like a measured one is the audio version
of that failure. The digest gives audio the property seeds give images — the same input
is recognisably the same output, and a hand-edited file is detectable.

Alternatives rejected:
- Emit times with no provenance: PHASE 8 would have to guess, or trust everything
  equally.
- Refuse to emit anything without alignment: blocks all downstream work on a dependency
  that may not be worth its cost.
- A boolean `estimated` flag: cannot express `aligned`, which is the state this is
  ultimately heading for.

Impact:
`absorbed_events` records every viseme dropped for being too short to read, so the
flicker rule (mapping.md §6) cannot quietly change the animation. Timings sum to the
audio duration exactly through every transformation.

---

## ADR-023 — PHASE 7 was built before the PHASE 6 gate passed
Date: 2026-08-27
Status: accepted

Context:
`PLAN.md` ("IMAGE PIPELINE GATE"), `CLAUDE.md` ("Phase Gate"), and `README.md` all state
that PHASE 6 must pass before any lip-sync, TTS, phoneme, or audio work begins. At the
time of this record `lock_library.py` reports GATE FAILED with 8 blocking problems and
0 of 38 image assets exist. PHASE 0 has never been run; there is no GPU environment and
no reference image.

Decision:
PHASE 7 was implemented anyway, on the explicit and repeated instruction of the
repository owner after the gate conflict was raised twice and restated. The gate itself
was not modified, weakened, or removed: `lock_library.py` still fails, and it still
reports PHASE 7 as closed.

Rationale:
The owner's instruction outranks the plan the owner wrote. Recording the override is
what keeps the gate meaningful — a rule quietly bypassed is worse than one explicitly
overridden with the cost written down.

What it costs, specifically:
- Nothing in PHASE 7 has been seen against a real mouth. Every duration and every shape
  is unvalidated against an actual viseme asset, because none exist.
- The Thai mapping is still unreviewed by a Thai speaker (PHASE 4.2), and PHASE 7 is the
  first consumer that depends on it being right.
- The duration model has never been checked against a measured alignment.
- mapping.md §6 names the first real test as the PHASE 8 lip-sync pass. That test is
  still ahead, and it now has more code riding on it.

Alternatives rejected:
- Refuse: the owner has the authority to sequence their own project, and the concern was
  already stated and overruled.
- Weaken the gate so PHASE 7 "passes" it: destroys the only mechanism protecting the
  image milestone, to make a document agree with reality.
- Build it untested and unmarked: the failure this repository keeps guarding against —
  an unverified artefact that looks verified.

Impact:
PHASE 8 remains blocked by the same gate, now for the same reasons plus more code
depending on unvalidated assumptions. `docs/audio/phase-7-audio-pipeline.md` §0 repeats
this status, and §8 lists what must happen before PHASE 8. The PHASE 6 gate is unchanged
and still failing.
