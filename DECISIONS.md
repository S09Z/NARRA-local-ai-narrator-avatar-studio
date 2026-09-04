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
Status: accepted; the "no package manager manifest" clause amended by ADR-029

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

---

## ADR-024 — The frame plan is a separate artefact from the render
Date: 2026-08-27
Status: accepted

Context:
PHASE 8 turns a viseme timeline into moving images. That could be one step — read the
timeline, composite frames, write PNGs — and for a first implementation it would be less
code.

Decision:
Two steps. `build_animation.py` produces `animation.json`: per frame, which visemes at
what weight, which expression underneath, and the idle tracks. `render_frames.py` reads
that and needs the whole image library. `validate_animation.py` checks the plan, not the
pixels.

Rationale:
The plan is the reviewable artefact. A wrong blend is visible as JSON — two layers where
there should be one, a closure at 0.8 weight, a hold of one frame — and invisible in a
video except as a mouth that looks slightly wrong. The same argument the repository
already makes for compiled prompts and generation metadata: record the decision, not just
the output.

It also means the engine can be built and validated before the assets exist, which is
what made PHASE 8 possible at all under ADR-027. That is a consequence and not the
justification; it would still be the right split with a full library.

Alternatives rejected:
- Render directly from the timeline: nothing to inspect, and no way to test any of
  8.1-8.4 without 38 images.
- Emit only frame numbers and let PHASE 9 decide weights: moves coarticulation into the
  renderer, where mapping.md's rules would have to be re-implemented per backend.

Impact:
`metadata/animations/*.json` is generated output and gitignored, like timelines.
`render_frames.py --check` reports required assets without decoding any.

---

## ADR-025 — Coarticulation encodes Thai articulation, not a generic crossfade
Date: 2026-08-27
Status: accepted

Context:
PLAN 8.2 asks for "smooth transitions using previous/current/next". A symmetric
crossfade between adjacent visemes satisfies that sentence completely, and gets Thai
wrong in three specific ways that `docs/thai-viseme/thai-viseme-mapping.md` names
explicitly.

Decision:
Three rules, in `docs/animation/coarticulation-model.json` with their sources attached:

1. An unreleased final holds. The transition out of a final stop is pushed entirely
   after the boundary rather than straddling it (mapping.md §3).
2. A closure must close. `MBP` is exempt from absorption and is pinned to full weight if
   blending would leave it short (mapping.md §5, CLAUDE.md).
3. A rounded vowel starts early. `U`, `O`, `AO` blend over 90ms weighted 70/30 towards
   the preceding consonant (mapping.md §6).

Rationale:
mapping.md §3 states that animating a release frame on a Thai final stop is the most
common way to make Thai lip-sync look foreign. That is a named failure mode, and a
symmetric crossfade produces it on every closed syllable — which in Thai is most of them.
Rule 2 is the same argument in the other direction: a bilabial that never fully closes is
not a smoother /p/, it is a different consonant, so smoothing must not be allowed to
delete it.

The rules live in a JSON file rather than in code because they are tunable once someone
watches a real pass, and because writing their sources next to their values is what keeps
them from being edited into arbitrary numbers later.

Alternatives rejected:
- A single symmetric crossfade: simpler, and wrong in the way the source document warns
  about by name.
- Per-phoneme hand-authored curves: unmaintainable across 16 visemes squared, and there
  is no observational basis for the values yet.
- Defer coarticulation to PHASE 9/GSAP: the rules are linguistic, not rendering
  concerns; every backend would have to re-implement them.

Impact:
The outgoing-phoneme test is deliberately narrow. PHASE 7 merges a final into a following
initial ("t̚+d"), and that initial does open into its vowel — suppressing that release
would be an error in the opposite direction, so only the last phoneme of an event is
consulted.

---

## ADR-026 — Frame-rate rules in frames; secondary animation as tracks
Date: 2026-08-27
Status: accepted

Context:
Two things PHASE 7 could not settle, because it did not know the frame rate or the
renderer. `mapping.md` §6 forbids a viseme held for one frame and PHASE 7 approximated
that as 0.060s, noting that PHASE 8 "decides the frame rate and may raise this". And PLAN
8.4 asks for blinking, breathing, head movement, and eyebrow movement, for a library that
contains 12 full-face expressions and no eye, brow, or head assets.

Decision:
The flicker rule is restated as `min_frames_on_screen: 2`. Shapes that cannot survive it
are absorbed into a neighbour and recorded in `mouth_meta.absorbed`; closures are exempt
and are extended instead (ADR-025).

Secondary animation is emitted as normalized keyframe tracks — blink spans, a breath
curve, two head-sway curves, brow accents — not as asset swaps. PHASE 9 binds them to
GSAP transforms. All jitter is seeded from the source timeline's digest.

Rationale:
0.060s is 1.5 frames at 25fps, which can quantise to one — the exact failure the rule
exists to prevent. Frames are what reach the eye, so the rule belongs in frames.

Tracks rather than swaps is forced by the library, but it is also the right split: PLAN
§9 already assigns head movement and camera to GSAP. Seeding from the timeline digest
gives idle motion the same reproducibility contract images get from a locked seed —
without it, two renders of one narration would differ and neither would be wrong.

Alternatives rejected:
- Keep the seconds-based minimum only: silently produces one-frame holds at low fps.
- Drop short visemes without recording them: the absorption note is how a user discovers
  that 25fps is eating their consonants.
- Random unseeded idle motion: unreproducible, and inconsistent with every other artefact
  in this repository.

Impact:
This surfaced a real gap: rendering a blink needs an eye region, and `ASSET_SPEC.md`
defines only a mouth anchor and mouth edit region. The gap is recorded in
`secondary-animation.json` and in the runbook §6 rather than worked around; blink timings
are still emitted, because the timing is a real decision even before it can be rendered.
Closing it is an asset-spec or PHASE 9 decision.

---

## ADR-027 — PHASE 8 was also built before the PHASE 6 gate passed
Date: 2026-08-27
Status: accepted

Context:
ADR-023 recorded PHASE 7 being built ahead of the image gate. PHASE 8 was then requested
the same way, after the objection was raised again and overruled again. The gate still
reports 8 blocking problems and 0 of 38 image assets.

Decision:
PHASE 8 implemented on explicit instruction. The gate was again not modified, weakened,
or removed.

Rationale:
Unchanged from ADR-023: the owner's instruction outranks the plan the owner wrote, and an
override recorded with its cost keeps the gate meaningful.

What it costs, and how this differs from ADR-023:
PHASE 7 was text and audio, and was fully testable — real Thai speech went in and a
validated timeline came out. PHASE 8 is images. Its entire purpose is to composite viseme
assets onto expression assets, and there are none. Every test runs against synthetic PNGs
generated in a temp directory.

That verifies the compositing contract — the mouth region changes and nothing else,
weights blend proportionally, closures reach full weight, finals do not release early —
and verifies nothing whatsoever about the character. Whether a real viseme reads as a
mouth moving on a real face is untested and untestable here. mapping.md §6 names the
PHASE 8 lip-sync pass as the first real test of the mapping; that pass has still not
happened.

The compounding is the actual cost. Two phases of tuned constants - blend windows,
anticipatory rounding, minimum holds, duration estimates - now sit on assumptions that
one look at a rendered frame could invalidate.

Alternatives rejected:
- Refuse: the objection was made twice and overruled twice; the sequencing is the owner's
  to decide.
- Build it without tests because assets are missing: the compositing contract is testable
  with synthetic assets, and untested code here would be the failure this repository
  keeps guarding against.
- Weaken the gate: destroys the only mechanism protecting the image milestone.

Impact:
PHASE 9 remains blocked by the same gate. `docs/animation/phase-8-lipsync-engine.md` §0
states plainly what is and is not verified, and §10 lists what must happen first. A guard
test asserts the repository's mouth anchor is still unmeasured — if it ever fails,
PHASE 4.3 has happened and rendering is live for real.

---

## ADR-028 — A Makefile fronts the existing checks; status reports, it does not judge

Date: 2026-08-28
Status: accepted

Context:
The repository has three real checks — the test suite, `compile_prompt.py --lint`, and
the PHASE 6 gate — and the facts about where the project stands are spread across a git
checkout, four asset directories, thirty-eight QC records, and the gate itself. Both were
reachable only by remembering the right command line. That is how a phase gets called
ready while its gate still reports eight problems.

Decision:
A `Makefile` with `test`, `lint`, `check`, `gate`, `status`, and `clean`, plus
`scripts/utilities/status.py` behind `status`. The Makefile runs existing scripts and
holds no logic of its own; every target stays runnable by hand.

Rationale:
The value is one obvious entry point, not automation. Putting logic in the Makefile
would make it a second implementation of the checks, which is the failure mode ADR-011
already guards against for canonical sets. `make` needs no install on macOS or Linux,
so ADR-007 (no package manifest, stdlib only) still holds.

Two constraints are deliberate, not incidental:

`status` always exits 0. It reports the gate's verdict without adopting it. A status
command that fails a build is a check wearing the wrong name, and the moment it can fail
someone starts working around it. `make gate` is the target that exits non-zero.

`clean` removes Python caches and nothing else. Generated images, timelines, frames, and
model weights are expensive to reproduce, already gitignored, and outside what a cache
cleaner should be trusted with (CLAUDE.md: never delete models). A `clean` that deletes
hours of generation once is a `clean` nobody runs again.

Alternatives rejected:
- A shell script per task: same content, no discoverable list, and no `make help`.
- A task runner dependency (just, invoke, tox): a new install to run checks that are
  already stdlib Python.
- Folding status into `lock_library.py --status`: the gate's job is to pass or fail on
  the image library; git state, prompt coverage, and PHASE 7/8 artefacts are not its
  business, and giving it a mode that cannot fail muddies the one thing it exists for.

Impact:
`make check` is the pre-commit pair. `make status` is the first command in a resumed
session — it currently reports the gate failing on 8 problems and 0 of 38 image assets,
which is the same answer ADR-023 and ADR-027 record, now without having to look it up.

---

## ADR-029 — Poetry manages the environment; it does not package the project

Date: 2026-08-28
Status: accepted, amending ADR-007

Context:
ADR-007 declined a package-manager manifest until PHASE 10. The reasoning was about
premature application scaffolding — a package, a CLI surface, an entry point — not about
environments. In practice the dependency surface (Pillow, pytest) was installed into
whatever interpreter happened to be on PATH, undeclared and unpinned, in a project whose
whole discipline is that a result must be reproducible from its record.

Decision:
`pyproject.toml` with `package-mode = false`, `poetry.toml` pinning the virtualenv to
`.venv/` in-project, and a committed `poetry.lock`. `make install` runs `poetry install`;
the Makefile uses `.venv/bin/python` when it exists and a bare `python3` otherwise.

Rationale:
`package-mode = false` is the whole reason this does not contradict ADR-007. Poetry
resolves, locks, and installs; it does not build NARRA, install it, or make it
importable. There is no package, no entry point, and no `narra` command. Scripts under
`scripts/` stay standalone and still find their shared modules through the explicit
`sys.path` insert of ADR-011. Nothing in the codebase changed to accommodate this.

What is gained is the part ADR-007 was never arguing against: the two dependencies are
declared instead of assumed, `poetry.lock` pins the exact versions a passing test run
was produced with, and the environment is isolated from the system interpreter. A
repository that records the seed, model, workflow, and sha256 of every image had no
record of the interpreter that validated it.

The Makefile falling back to `python3` is deliberate. Poetry is how you get an
environment, not a requirement to run anything — every script must stay executable by
someone who cloned the repo and has Pillow installed. The moment `make status` needs
Poetry, the tooling has grown a dependency the scripts themselves do not have.

Alternatives rejected:
- `requirements.txt` + `python -m venv`: no lock file and no resolver, so "what was this
  validated with" stays unanswerable — the exact gap being closed.
- Poetry in package mode: creates the `narra` package and CLI surface that ADR-007
  correctly defers to PHASE 10, and to no current benefit.
- Nothing, per ADR-007 as written: the clause was about scaffolding an application, and
  applying it to environment management leaves the dependencies undeclared for a reason
  the ADR does not actually give.

Impact:
`make install` then `make check` is the setup path. PHASE 10 packaging is still open and
still needs its own decision — flipping `package-mode` is the smaller half of it. The
PHASE 0 runbook's `pip install -r requirements.txt` remains ComfyUI's own requirements
file under `~/ComfyUI`, unrelated to this manifest.

---

## ADR-030 — Correction is a separate tool from validation

Date: 2026-08-28
Status: accepted

Context:
The first real candidate failed three checks: 1254x1254 against a required 1024x1024,
32.45% semi-transparent against a 6% limit, and 0.12% opaque against a 10% minimum. The
alpha histogram showed why — 67.4% at exactly 0 and the character body at 253/254, with
only 0.58% of pixels genuinely part-transparent. The cutout was clean; a lossy encode
had moved the body off exact opacity, and `imagecheck.check_pixels` tests `== 255`, so
alpha 254 scores identically to alpha 128. The reported "soft matte or halo" was wrong.

The reflex fix is to widen the thresholds. That would have been the wrong repair: it
loosens a check on the one image every other asset is derived from, in order to work
around a defect that a resize and an alpha snap remove entirely.

Decision:
`scripts/utilities/prep_reference.py` applies the mechanical corrections — snap alpha
>=250 to 255 and <=5 to 0, downscale to 1024x1024 — and re-runs the automated checks on
what it wrote. `validate_reference.py` is unchanged and still edits nothing. No
threshold moved.

Rationale:
A validator that edits its input cannot be trusted about what it validated, so the two
stay separate processes with separate exit codes. Correction never overwrites the
candidate: the original is the record of what was actually generated.

The snap window is the load-bearing choice. 250-255 and 0-5 is wide enough for encode
quantisation and far too narrow to flatten a real soft edge, which spreads across the
whole range rather than clustering at the ends. To make that a guarantee rather than a
hope, prep measures the genuinely part-transparent fraction (alpha 6-249) first and
refuses outright above the same 6% the spec uses. A real matte cannot be snapped into a
false pass; it is a generation defect and the tool says so.

It also refuses a non-square candidate rather than resizing it — squashing a face to fit
is silent damage of exactly the kind ASSET_SPEC exists to prevent. `--pad` letterboxes
onto transparent instead, which is lossless when the background is already empty.

Alternatives rejected:
- Raise MAX_SEMI_TRANSPARENT_FRACTION or lower MIN_OPAQUE_FRACTION: weakens the check
  protecting the source of truth for all 38 assets, permanently, to fix one encode.
- Change REQUIRED_SIZE to accept 1254: 1024 is wired into the anchor tolerances (0.5%
  drift = 5px at 1024) and the 2048 upscale rule, and the candidate is already 1:1, so a
  clean downscale costs nothing.
- Fold correction into `validate_reference.py --fix`: makes the validator an editor.
- Do it by hand each time: unrecorded and unrepeatable, in a repository whose whole
  discipline is that a result is reproducible from its record.

Impact:
The candidate now passes all nine automated checks with no threshold changed.
`character/reference/README.md` §3 carries prep as step 2a. Whether the exact-255 test
in `imagecheck.check_pixels` should become tolerance-based is a separate question about
what ASSET_SPEC §4 means, deliberately not settled here.

---

## ADR-031 — The ordered procedure is a document; the first run is a command

Date: 2026-09-02
Status: accepted

Context:
The repository answers "what are the phases" (`PLAN.md`), "what must an asset satisfy"
(`ASSET_SPEC.md`), and "why is it built this way" (`DECISIONS.md`), but the question a
person actually arrives with — *what do I run next, and where does it stop* — had no
home. Answering it meant assembling eight commands out of four documents and then
knowing which failures are work waiting for a person and which are the RTX 5070 this
laptop is not. `make status` reports where the project stands; it does not say what to
do about it, and deliberately should not.

Decision:
Two artefacts, not one. `GUIDELINE.md` is the ordered procedure — fifteen steps as of PHASE 9, each
naming the machine it runs on, the commands, the pass criterion, and what it blocks.
`scripts/utilities/demo_run.py`, behind `make demo`, walks the checkable subset of those
steps, prints the real command before running it, and reports `OK` / `TODO` / `BLOCKED`.

Rationale:
A document alone goes stale silently. A command alone cannot explain why the order is
the order — why the bible precedes generation, why the anchor is measured once, why
replacing the reference is a full library regeneration. Splitting them lets each do what
it is good at, and the demo printing its commands verbatim is what keeps the two honest:
a reader can run any line of the tour by hand and get the same answer.

Three constraints are deliberate:

The walkthrough **writes nothing**. It generates no image, records no metadata, installs
no dependency. A first-run command that quietly creates files is one nobody can point at
a live library, which would make it useless exactly when it is most wanted. A test pins
this by hashing the tree before and after.

It **always exits 0**, for the reason ADR-028 gives for `status`. The gate is
`lock_library.py`; a tour that can fail a build is a check wearing the wrong name.

It **reports `BLOCKED` rather than simulating**. The generation steps need ComfyUI and
the GPU. Faking them with placeholder assets would put fabricated images one careless
copy away from `character/`, and would teach the pipeline's shape while hiding the only
fact that currently matters — that 0 of 38 assets exist.

Alternatives rejected:
- Folding the procedure into `README.md`: the README orients a reader; a fifteen-step
  runbook buried in it serves neither purpose.
- Extending `status.py` with a `--walkthrough` mode: status collects facts and prints
  them. Running eight subprocesses and teaching an order is a different job, and ADR-028
  already argues against giving a reporting tool a second personality.
- A `--demo` flag that generates placeholder assets so the whole pipeline "runs":
  rejected on ADR-003 grounds. Nothing that is not a real reference edit should ever
  exist in a shape that could be mistaken for a library asset.

Impact:
`make demo` is the first command in a fresh checkout, and `GUIDELINE.md` is what
`README.md` points at for the procedure. On this tree the tour reports OK 3 / TODO 3 /
BLOCKED 2, and names filling the character bible as the next action — the same answer
`make status` gives, arrived at by walking the steps rather than by knowing where to
look. When a step's command changes, the demo breaks loudly and the guideline must be
edited with it; that coupling is the point.

---

## ADR-032 — HyperFrames and GSAP are render targets, not dependencies

Date: 2026-09-03
Status: accepted

Context:
PLAN §9 names HyperFrames as the compositor, timeline engine, subtitle renderer,
camera and final renderer, and GSAP as the thing driving mouth, head, camera, text,
and expression transitions. Neither is present in this repository. HyperFrames appears
in no file outside the planning documents, is not installed, and cannot be inspected,
version-pinned, or checked for conflicts — the three things `CLAUDE.md` requires before
a dependency is added. GSAP is a browser animation library and implies a Node runtime
and a headless browser, a dependency surface larger than the entire project, which
today is Pillow and pytest (ADR-029).

Decision:
PHASE 9 produces a **video plan**: a complete, validated, renderer-independent document
describing the finished video. Renderers are adapters over it, in the sense ADR-021
gives the word for TTS. `ffmpeg` is the reference engine and the only implemented one.
`hyperframes` is declared in `docs/video/render-profile.json` with status
`"declared, not implemented"` and the reason it is blocked, and `validate_video.py`
fails any plan that names an unimplemented engine.

Two properties make the plan portable rather than merely ffmpeg-shaped. Camera motion
carries GSAP easing names, so a GSAP renderer reproduces the curve instead of guessing
at it. And camera motion also carries the curve already sampled, one entry per frame,
with the plan marking `"authoritative": "frames"` — the samples are the contract, so
two renderers agree by reading the same numbers rather than by easing alike.

Rationale:
Wiring up a tool that cannot be run here would produce code nobody has executed, in a
phase already three gates ahead of its assets. Declaring it and building the artefact
it would consume costs nothing now and makes adding it later an adapter rather than a
rewrite. It also keeps the honest answer visible in the artefacts: a plan says which
engine made it, and the engine registry says which engines are real.

Alternatives rejected:
- Implement a GSAP renderer through Playwright: adds Node, a browser, and a headless
  screenshot pipeline to encode 118 frames that Pillow composites directly. The browser
  would be doing compositing, not animation, since the tracks are already sampled.
- Wait for HyperFrames before building PHASE 9: leaves subtitles, camera, and the plan
  format unbuilt for an unknown period, when all three are decidable now.
- Treat ffmpeg as the only engine and drop the abstraction: PLAN §9 names HyperFrames,
  and silently dropping a named requirement is not a decision, it is an omission.

Impact:
No MP4 has been produced — ffmpeg is not installed on the development machine, so the
encode path has never run. `render_video.py --check` reports that per requirement.
`ffmpeg_command()` is a pure function returning argv, so the exact call is tested
without an encoder present.

---

## ADR-033 — Thai subtitles break at word boundaries recovered from the PHASE 7 parse

Date: 2026-09-03
Status: accepted

Context:
Thai is written without spaces between words. Every general-purpose subtitle wrapper
breaks on whitespace or on a character count, and both are wrong here: a character-count
break splits a word, orphans a final consonant, or lands between a consonant and the
vowel or tone mark that sits on it. The last case does not produce an ugly line, it
produces a different string. PHASE 7 already segments the sentence to phonemize it, so
the boundary information exists; the timeline just does not store it.

Decision:
Cues are built from the PHASE 7 segmentation, re-derived from the text the timeline
records. The timeline's recorded syllable count is checked against the re-parse and a
mismatch is refused, because a parse that changed under a timeline would give the right
mouth shapes to the wrong words with nothing downstream noticing.

Three additions to `thai_g2p.py` support it, placed there rather than in PHASE 9 because
that module owns segmentation (ADR-011):

- `Syllable.span` — where a syllable came from, in the normalised text. Text alone is
  not enough: a lexicon entry covers several syllables, and two adjacent identical words
  would collapse into one.
- `normalise_map()` — `normalise()` plus the index of the source character behind every
  surviving one. `normalise()` now delegates to it, so there is one implementation.
- `base_span()` — the inverse walk, back over what normalisation deleted.

Rationale:
Normalisation strips exactly the characters a reader most needs: tone marks, because
tone does not change mouth shape, and consonants silenced by thanthakhat. Displaying
the normalised form would show `วันนี` for `วันนี้` and `สตาง` for `สตางค์` — different words,
in a subtitle, in the product's own language. Mapping back is the only way to have
correct phonemes and correct spelling from one parse.

Alternatives rejected:
- Wrap on character count: the failure this exists to prevent.
- Add a Thai word segmenter (pythainlp, ICU): a third dependency, a second segmentation
  that would disagree with the one driving the visemes, and two different notions of
  where a word ends in the same video.
- Store syllable spans in the timeline: changes the PHASE 7 schema for a PHASE 9 need,
  and the information is derivable from what is already recorded.
- Re-implement the normalisation index map inside `subtitle.py`: a second copy of
  stripping rules that would drift from the first.

Impact:
`tests/audio/test_thai_g2p.py` gained span and mapping tests; the existing 21 pass
unchanged. Line breaking is only as good as the parse — the same parse whose viseme
mapping is still unreviewed by a Thai speaker (PHASE 4.2). The reading-speed and line-
length numbers in `subtitle-style.json` come from the Netflix Thai style guide and are
equally unreviewed.

---

## ADR-034 — Camera moves are bounded by source resolution and camera class

Date: 2026-09-03
Status: accepted

Context:
A camera move in this pipeline is a transform over rendered 1024x1024 avatar frames. It
cannot generate detail. Past a certain scale a push-in stops being a camera move and
becomes an upscale, and the character's identity — the thing six phases of work exist
to hold stable — degrades in a way no downstream step can repair.

Decision:
`docs/video/camera-model.json` carries the numeric limits and `camera.check_limits()`
holds every plan to them. Two bounds are about pixels: `max_sampling_ratio` of 1.0
(never draw a source pixel larger than one output pixel) and hard `max_scale` /
`min_scale`. Two are about motion: `max_scale_change_per_second` and
`max_pan_fraction`. One is about framing: scale may not take the head past what a
close-up asset shows, derived as `1 / class_ratio` from `visual-spec.md` §2 (ADR-014).

The numeric bounds fail. The framing bound and the sampling ratio warn.

Rationale:
The avatar draws at 886px from a 1024px source at rest, so there is real headroom, and
refusing every push-in outright would make the shipped `slow-push` preset unusable. But
a 1.3x push on a `three-quarter` pose is a 1.16 sampling ratio — visibly soft — and
that has to be said. Splitting fail from warn along "the model's own numbers" versus
"a creative call with a cost" keeps `--strict` meaningful: a release render can turn
every warning into a failure, and an iteration render need not.

Alternatives rejected:
- Allow any scale and rely on judgement: the whole repository is built on the opposite
  premise, that the checkable things are checked.
- Fail on any upscale: `slow-push` at 1.08 on a close-up asset is ordinary filmmaking
  and looks fine; a rule that forbids it would be routed around.
- Render at the source resolution and never scale: gives up camera movement entirely,
  which PLAN §9 asks for by name.

Impact:
Every preset in the model is tested against the limits the same file declares, so a
shipped move that violates a shipped limit is a test failure rather than a surprise.
`max_scale_change_per_second` is a judgement made without having watched footage, and
is listed for re-tuning in `docs/video/phase-9-video-pipeline.md` §8.

---

## ADR-035 — Subtitles ship as a timed-text sidecar; burn-in goes through libass

Date: 2026-09-03
Status: accepted

Context:
PLAN §9 lists subtitle rendering. The obvious implementation — draw the text onto each
frame with Pillow, which is already a dependency — does not work for Thai. Pillow shapes
complex scripts only when built against Raqm, and `PIL.features.check("raqm")` is
`False` on the development machine. Without shaping, Thai tone marks and vowel signs are
positioned by glyph advance: they render beside the consonant instead of above or below
it. The text is legible enough to pass a glance and wrong to any Thai reader.

Decision:
Subtitles are emitted as a sidecar file — SRT by default, ASS when styling is needed —
and burn-in is off by default. When a plan does ask for burn-in, the text is drawn by
ffmpeg's libass, which shapes through HarfBuzz unconditionally, and never by Pillow.
`validate_video.py` fails a plan that sets `burn_in` without the `.ass` format, and
`render_video.py --check` probes for libass in the installed ffmpeg and refuses without
it. Pillow composites the avatar and never draws a glyph.

Rationale:
Shaping is the deciding constraint, but the sidecar earns its place twice over. This
pipeline still needs a Thai speaker to review the viseme mapping, outstanding since
PHASE 4.2; the subtitle timing now needs the same review. An `.srt` is a file a
reviewer can open, correct, and hand back. Text burned into pixels cannot be corrected
without re-rendering, and cannot be diffed at all.

Alternatives rejected:
- Require a Raqm-enabled Pillow: a build-flag dependency that cannot be expressed in
  `pyproject.toml`, and would fail silently on any machine without it — the exact
  failure mode this avoids.
- Draw with ffmpeg's `drawtext` filter: does not shape either, so it fails the same way.
- Burn in by default because "a narration video needs open captions": true for
  distribution, and a decision for the person publishing, made once with a
  `--burn-in` flag rather than baked into every render.

Impact:
No burned-in render has been produced or verified, because no ffmpeg is installed to
verify it with. The claim that libass shapes Thai correctly is from its documentation,
not from this pipeline's output, and stays untested until §8 of the phase doc is worked
through.

---

## ADR-036 — PHASE 9 was also built before the PHASE 6 gate passed

Date: 2026-09-03
Status: accepted, under protest recorded

Context:
`CLAUDE.md` blocks lip-sync, HyperFrames, TTS, audio, and video work until the image
library is production-locked. PHASE 7 was built ahead of it on explicit instruction
(ADR-023) and PHASE 8 on the same (ADR-027). PHASE 9 was requested the same way. The
gate still fails on 7 blocking problems with 0 of 38 image assets.

Decision:
Build it, on the same terms as ADR-023 and ADR-027: the gate is not modified, not
weakened, and not worked around; every claim about what has been verified is scoped to
what was actually run; and this entry records the cost.

Rationale:
The instruction is explicit and repeated, and the phase is not idle work — the video
plan, the Thai subtitle segmentation, and the camera limits are all decidable without a
single generated asset, and all three were exercised against real Thai text and real
PHASE 7/8 artefacts. What cannot be exercised is named rather than simulated.

The cost differs from PHASE 7's and PHASE 8's, and is worth stating exactly. PHASE 7
was text and audio and was fully testable. PHASE 8 composites images that do not exist,
and was tested against synthetic PNGs. PHASE 9 inherits that gap and adds a second one:
its output stage needs ffmpeg, which is not installed here, so the encode path has
never run at all — not against synthetic data, not against anything.

Alternatives rejected:
- Refuse until PHASE 6 passes: the instruction was explicit and repeated across three
  phases; a refusal here would be re-litigating a settled decision.
- Simulate an encode so the path appears exercised: would put an untested claim into
  the record, which is the one thing these ADRs exist to prevent.

Impact:
Three phases now depend on assets that do not exist, and one depends on a binary that
is not installed. `make demo` and `make status` both report the gate failing.
Nothing in PHASE 7, 8, or 9 should be described as working until a real asset has been
generated, composited, and encoded.
