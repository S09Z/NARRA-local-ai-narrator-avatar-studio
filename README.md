# NARRA — Local AI Narrator Avatar Studio

Local-first FLUX.2 + ComfyUI avatar generation pipeline for Thai-language narrator content.

## Current Milestone

Image generation only.

The project does not implement lip-sync/video until the image asset library is stable.

## Start

Read:

1. `CLAUDE.md`
2. `PLAN.md`
3. `DESIGN.md`
4. `MEMORY.md`

## Core Pipeline

Reference Avatar
→ Character Consistency
→ Expressions
→ Thai Visemes
→ Poses
→ QC
→ Production Lock

Later:

Audio
→ Thai Phoneme
→ Viseme
→ Animation
→ HyperFrames
→ MP4

## Quick Start

This repository is **structure and documentation only**. No models, no Python
environment, no ComfyUI installation is included or assumed yet — that is PHASE 0 work.

1. Read `CLAUDE.md` — project rules, quality gates, safety rules.
2. Read `PLAN.md` — phases, milestones, acceptance criteria.
3. Read `DESIGN.md` — architecture and subsystem boundaries.
4. Read `MEMORY.md` — current status and durable constraints.
5. Start at **PHASE 0 — Environment & Architecture**.

Reference docs, consulted as needed:

| Document             | Use it for                                            |
|----------------------|-------------------------------------------------------|
| `PROMPT_GUIDE.md`    | Prompt architecture, preservation and viseme rules    |
| `ASSET_SPEC.md`      | Resolution, naming, mouth anchor, QC, metadata schema |
| `DECISIONS.md`       | Why the architecture is the way it is                 |
| `TROUBLESHOOTING.md` | ComfyUI, VRAM, model, node, and consistency failures  |

## Directory Structure

```
.
├── CLAUDE.md              AI agent instructions, rules, quality gates
├── PLAN.md                Phases, milestones, acceptance criteria
├── DESIGN.md              Architecture and subsystem boundaries
├── MEMORY.md              Durable facts and current status
├── DECISIONS.md           Architectural decision record
├── PROMPT_GUIDE.md        Prompt architecture and rules
├── ASSET_SPEC.md          Asset technical specification
├── TROUBLESHOOTING.md     Diagnostics
├── README.md
├── .gitignore
│
├── character/             Canonical, approved character assets
│   ├── reference/           master reference image (source of truth)
│   ├── bible/               character bible, visual spec, mouth anchor
│   ├── expressions/         12 approved expressions
│   ├── visemes/             16 approved Thai visemes
│   └── poses/               10 approved narrator poses
│
├── prompts/               Versioned prompt sources
│   ├── master/              master character prompt
│   ├── expressions/         one prompt per expression
│   ├── visemes/             one prompt per viseme
│   └── poses/               one prompt per pose
│
├── workflows/             ComfyUI workflow JSON, small and single-purpose
│   ├── flux/                base text-to-image
│   ├── reference-edit/      reference editing (backbone workflow)
│   ├── expression/
│   ├── viseme/
│   └── pose/
│
├── models/                Local model weights — never committed
│   ├── checkpoints/  vae/  lora/  text_encoders/  controlnet/
│
├── assets/                Working asset flow
│   ├── input/               source material
│   ├── generated/           raw output — not committed
│   ├── approved/            passed QC
│   └── contact-sheets/      side-by-side review sheets
│
├── metadata/              Reproducibility records
│   ├── generations/         per-asset generation metadata
│   ├── prompts/             compiled prompt records
│   └── validation/          QC results
│
├── scripts/               Standalone utilities (no app framework)
│   ├── setup/  generation/  validation/  utilities/
│
├── tests/
│   ├── prompts/  assets/  validation/
│
├── docs/
│   ├── architecture/  workflows/  thai-viseme/  operations/
│
└── .claude/
    ├── skills/push-draft-pr/   milestone → Draft PR skill (placeholder)
    └── commands/
```

## Development Workflow

Per-change loop (from `CLAUDE.md`):

```
inspect → understand → propose → implement → test → report
```

Per-milestone loop:

1. Read `PLAN.md`; identify the current milestone and its acceptance criteria.
2. Confirm the previous phase gate passed.
3. Implement only that milestone.
4. Validate against the acceptance criteria — and against `ASSET_SPEC.md` §10 for any
   generated asset.
5. Record metadata for every approved asset (`ASSET_SPEC.md` §11).
6. Record any architectural decision in `DECISIONS.md`; update status in `MEMORY.md`.
7. Commit on a feature branch and open a Draft PR.

Hard rules:

- **PHASE 6 gates PHASE 7.** No lip-sync, TTS, phoneme analysis, HyperFrames, or video
  rendering work before the image asset library is production-locked.
- Model weights and raw generations are never committed. Approved character assets are
  committed only on explicit approval.
- Custom ComfyUI nodes require justification, version pinning, and a record in
  `docs/operations/` before installation.
- A locked asset must be reproducible from its metadata alone.
