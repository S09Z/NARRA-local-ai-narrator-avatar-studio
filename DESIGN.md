# DESIGN.md

# NARRA — System Design

## Design Goal

Separate image generation from video/lip-sync so each subsystem can be validated independently.

## Architecture

Reference Avatar
→ Character Bible
→ Prompt Compiler
→ ComfyUI Workflow
→ FLUX.2 Klein 4B
→ Asset Validator
→ Approved Asset Library

Later:

Audio
→ Thai Phoneme
→ Viseme Mapper
→ Animation Timeline
→ HyperFrames/GSAP
→ MP4

## Core Principles

1. Reference-first
2. Edit instead of regenerate when possible
3. Character identity is immutable unless explicitly changed
4. Expression and mouth are separate layers
5. Deterministic generation
6. Minimal dependencies
7. Local-first
8. Video pipeline remains separate from image pipeline

## Asset Layers

Character:
- base/reference
- expression
- eyes
- eyebrows
- mouth/viseme
- pose

The system should allow composition rather than requiring every combination to be generated as a unique image.

## Model Strategy

Fast:
FLUX.2 Klein 4B Distilled

Quality:
FLUX.2 Klein 4B Base

Optional future:
Narrator LoRA

LoRA is not part of the critical path.

## Workflow Strategy

Small workflows:
- reference edit
- expression
- viseme
- pose
- upscale
- batch

Avoid monolithic graphs.

## Reproducibility

Every approved asset has:
- seed
- model
- workflow
- prompt version
- reference
- metadata

## Quality Gate

No asset enters the production library without visual consistency validation.

## Future Video Boundary

The image subsystem produces assets.

The video subsystem consumes assets.

Do not mix responsibilities.
