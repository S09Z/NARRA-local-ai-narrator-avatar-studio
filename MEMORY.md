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

Phase 0: not started — no ComfyUI, no models, no GPU environment yet.
Phase 1: scaffolding complete, blocked on inputs. GATE NOT PASSED.
Phase 2: prompt system complete, blocked on the same inputs.
Phase 3–6: planned.
Phase 7–10: planned, blocked by image-generation gate.

### Phase 1 — Reference Avatar Foundation

| Step | Deliverable | Status |
|------|-------------|--------|
| 1.1 Import reference | `character/reference/` importer + spec checks | Ready — **awaiting the reference image** |
| 1.2 Character bible  | `character/bible/character-bible.md` | Structure complete — identity fields awaiting the reference image |
| 1.3 Visual spec      | `character/bible/visual-spec.md`, `mouth-anchor.json` | Structure complete — measurements awaiting the reference image |
| 1.4 Baseline tests   | `tests/assets/phase1-baseline.md` | Protocol written — **blocked on the PHASE 0 gate** |

Two inputs unblock the rest of Phase 1:

1. The canonical reference image (1024x1024 PNG RGBA, transparent background, neutral
   expression, REST mouth). Import with
   `python3 scripts/validation/validate_reference.py <file> --import`.
2. A working PHASE 0 environment on the RTX 5070 machine. The baseline tests in 1.4
   cannot run without ComfyUI and the Klein 4B models.

### Phase 2 — Prompt & Character Consistency

| Step | Deliverable | Status |
|------|-------------|--------|
| 2.1 Master prompt    | `prompts/master/master-character-v1.0.md` | Structure complete — slots filled from the bible |
| 2.2 Prompt variables | `prompts/README.md`, `scripts/generation/compile_prompt.py` | Complete |
| 2.3 Versioning       | filename + header versioning, enforced by `--lint` | Complete |
| 2.4 Deterministic seeds | seed = range base + canonical index | Complete |
| 2.5 Reference-edit tests | `tests/assets/phase2-reference-edit.md`, `prompts/diagnostic/` | Prompts written — **blocked on the PHASE 0 and PHASE 1 gates** |

The same two inputs unblock Phase 2. Nothing in Phase 2 has been validated against a
real generation.

## Decision Log

Add dated decisions here.

Format:

### YYYY-MM-DD — Decision
Context:
Decision:
Reason:
Impact:

### 2026-08-25 — Reference filename, diagnostic seeds
Context: PHASE 1 implementation surfaced two unspecified details.
Decision: Reference is `narra-reference-master-v1.png` with a byte-identical `master.png`
alias (ADR-008). Diagnostic and gate-test generations use seeds 1000–1999 (ADR-009).
Reason: Version history on the reference without rewriting workflow JSON on every bump;
diagnostic runs must not share seed space with library assets.
Impact: Enforced by `scripts/validation/validate_reference.py --check-imported`.

### 2026-08-25 — Preservation and negatives are generated
Context: The fixed PRESERVATION template and negative groups contradict themselves when
the TASK targets a feature they name.
Decision: Prompts declare `touches`; the compiler builds the preserved list and filters
negative terms from it (ADR-010).
Reason: A self-contradicting prompt produces unstable output that gets blamed on the model.
Impact: `PROMPT_GUIDE.md` §3 and §8 rewritten. Enforced by `compile_prompt.py --lint`.

## Full Decision Records

Dated architectural decisions with rationale and rejected alternatives live in `DECISIONS.md`.
This file keeps the short-form status; `DECISIONS.md` keeps the reasoning.
