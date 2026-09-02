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
| `docs/workflows/`    | Per-phase runbooks, including the PHASE 6 lock        |
| `docs/audio/phase-7-audio-pipeline.md` | Thai TTS, G2P, and viseme timelines (PHASE 7) |
| `docs/animation/phase-8-lipsync-engine.md` | Coarticulation, layering, and frame plans (PHASE 8) |
| `docs/production-baseline.md` | What the locked library was produced with (generated) |

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
├── Makefile              Dev tasks: install, test, lint, check, gate, status, clean
├── pyproject.toml         Dependencies — environment only, package-mode = false
├── poetry.lock            Pinned versions
├── poetry.toml            Keeps the virtualenv at .venv/ in-project
├── .gitignore
│
├── character/             Canonical, approved character assets
│   ├── reference/           master reference image (source of truth)
│   ├── bible/               character bible, visual spec, mouth anchor
│   ├── compositions/        narrator states — recipes over the asset layers
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
│   │   └── upscaled/          2048 derivatives of locked masters
│   └── contact-sheets/      side-by-side review sheets
│
├── metadata/              Reproducibility records
│   ├── generations/         per-asset generation metadata
│   ├── prompts/             compiled prompt records
│   ├── validation/          QC results and human sign-offs
│   ├── timelines/           PHASE 7 viseme timelines
│   ├── animations/          PHASE 8 frame plans
│   └── production-lock.json  PHASE 6 lock — written by lock_library.py
│
├── scripts/               Standalone utilities (no app framework)
│   ├── setup/  generation/  validation/  utilities/
│   │             prep_reference.py — correct a candidate to ASSET_SPEC
│   ├── audio/               PHASE 7 — TTS and timeline CLIs
│   ├── animation/           PHASE 8 — frame plan and render CLIs
│   └── lib/                 shared modules (canon, imagecheck, g2p, timeline, animation)
│
├── tests/
│   ├── prompts/  assets/  validation/  utilities/  audio/  animation/
│
├── docs/
│   ├── architecture/  workflows/  thai-viseme/  operations/
│   ├── audio/               PHASE 7 runbook, duration model, G2P lexicon
│   └── animation/           PHASE 8 runbook, coarticulation and idle models
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

### Dev tasks

Setup, once:

```bash
make install     # poetry install — creates .venv/ and installs Pillow + pytest
make check       # test + lint, on that .venv
```

`make` is the entry point for the checks this repository already has. Every target is a
script that is equally runnable by hand. The interpreter is `.venv/bin/python` when one
exists and a bare `python3` otherwise — Poetry is how you get an environment, not a
requirement to run anything (`DECISIONS.md` ADR-029). Override with
`make test PYTHON=/usr/bin/python3.12`.

| Task | What it runs |
|---------------|--------------------------------------------------------------|
| `make help` | the target list (default) |
| `make install` | `poetry install` — dependencies into `.venv/` |
| `make test` | `pytest tests/` |
| `make lint` | `compile_prompt.py --lint` — prompt structure, preservation, seeds |
| `make check` | `test` + `lint`, the pre-commit pair |
| `make gate` | `lock_library.py` — the PHASE 6 gate, reports only |
| `make status` | `status.py` — git, prompts, library, gate verdict, next step |
| `make clean` | Python caches only; never assets, models, or metadata |

The dependency surface is two packages — Pillow and pytest — declared in `pyproject.toml`
and pinned in `poetry.lock`. `package-mode = false`: Poetry manages the environment and
does not package NARRA, so there is no `narra` package, module, or command to import
(ADR-007, ADR-029). Adding a third dependency is a decision — see `CLAUDE.md`.

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

- **PHASE 6 gates PHASE 9.** No HyperFrames or video rendering work before the image
  asset library is production-locked. PHASE 7 (Thai audio / phoneme) and PHASE 8
  (lip-sync engine) were both built ahead of this gate on explicit instruction, and are
  recorded with what they cost in `DECISIONS.md` ADR-023 and ADR-027. The gate itself was
  not modified: `lock_library.py` still fails on 8 problems, and 0 of 38 image assets
  exist. PHASE 8 is tested only against synthetic assets — no real viseme has been
  composited onto a real expression.
- Model weights and raw generations are never committed. Approved character assets are
  committed only on explicit approval.
- Custom ComfyUI nodes require justification, version pinning, and a record in
  `docs/operations/` before installation.
- A locked asset must be reproducible from its metadata alone.
