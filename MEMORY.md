# MEMORY.md

# NARRA Project Memory

This file stores durable project decisions.

## Current Goal

Generate consistent narrator avatar images locally before implementing lip-sync video.

## Project Name

NARRA — Local AI Narrator Avatar Studio

## Hardware

- RTX 5070 12GB
- 32GB RAM

## Primary Model

FLUX.2 Klein 4B Distilled

## Quality Model

FLUX.2 Klein 4B Base

## Canonical Asset Targets

Expressions:
12

Thai Visemes:
16

Poses:
10

## Thai Viseme Set

REST, A, I, U, E, O, AE, AO, MBP, FV, TH, KG, S, SH, L, N

## Important Decisions

- Image generation is the first milestone.
- Video/lip-sync is blocked until image assets are production-locked.
- Prefer reference editing over full regeneration.
- Keep expression and viseme layers independent.
- Avoid unnecessary custom nodes.
- LoRA is optional and not part of the initial critical path.
- HyperFrames belongs to the later video/compositing phase.

## Current Status

Phase 0–6: planned.
Phase 7–10: planned, blocked by image-generation gate.

## Decision Log

Add dated decisions here.

Format:

### YYYY-MM-DD — Decision
Context:
Decision:
Reason:
Impact:

## Full Decision Records

Dated architectural decisions with rationale and rejected alternatives live in `DECISIONS.md`.
This file keeps the short-form status; `DECISIONS.md` keeps the reasoning.
