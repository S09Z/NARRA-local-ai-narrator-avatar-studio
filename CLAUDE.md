# CLAUDE.md

## Project

NARRA — Local AI Narrator Avatar Studio.

Purpose: build a local-first FLUX.2 + ComfyUI pipeline for generating consistent 2D narrator avatar assets for Thai-language content.

Future integration:
- Thai TTS
- Thai phoneme analysis
- Viseme lip-sync
- HyperFrames
- GSAP
- Automated video rendering

## Current Priority

IMAGE FIRST.

Do not begin video/lip-sync implementation until the image-generation milestone is locked.

The current objective is:

Reference Avatar → Character Consistency → Expressions → Thai Visemes → Poses → QC → Production Lock

## Hardware

Primary target:
- NVIDIA RTX 5070
- 12GB VRAM
- 32GB RAM

Default model:
- FLUX.2 Klein 4B Distilled

Quality/editing model:
- FLUX.2 Klein 4B Base

Do not make 20GB+ VRAM models a default requirement.

## Character Source of Truth

The canonical reference image is authoritative.

Preserve unless explicitly requested:
- face proportions
- head shape
- hairstyle
- hair color
- eyes
- eyebrows
- skin tone
- clothing
- accessories
- art style
- line style
- lighting style

If the request says "change only the mouth", change only the mouth.

## Thai Viseme Set

Use a practical visual viseme set:

REST, A, I, U, E, O, AE, AO, MBP, FV, TH, KG, S, SH, L, N

This is a visual animation approximation, not a complete Thai phonological model.

MBP must be visually distinct from REST.

## Prompt Architecture

Use structured prompts:

CHARACTER
+ PRESERVATION
+ TASK
+ EXPRESSION
+ VISEME
+ POSE
+ CAMERA
+ LIGHTING
+ STYLE
+ OUTPUT

Prefer concrete visual instructions over vague adjectives.

## Reference Editing

Prefer image editing over full regeneration when changing a specific facial or visual feature.

For mouth/viseme generation:

reference → mask/edit → FLUX.2 → viseme

Always explicitly preserve unrelated character features.

## ComfyUI Policy

Prefer native ComfyUI nodes.

Required:
- ComfyUI
- ComfyUI Manager

Recommended only when justified:
- rgthree-comfy
- KJNodes
- Impact Pack

Do not install custom nodes merely because they are popular.

Before adding a dependency:
1. explain why it is needed
2. verify compatibility
3. record repository/version
4. check for dependency conflicts

## Performance

Optimize for RTX 5070 12GB.

Prefer:
- FP8 where appropriate
- batch size 1
- 1024x1024 generation
- model reuse
- minimal node graphs
- sequential generation

Avoid:
- unnecessary ControlNet stacks
- unnecessary LoRA stacks
- duplicate model loading
- huge batches
- 4K generation during iteration

Do not use --lowvram by default.

## Asset Structure

character/
- reference/
- expressions/
- visemes/
- poses/

prompts/
- master/
- expressions/
- visemes/
- poses/

workflows/
scripts/
metadata/
docs/
tests/

## Metadata

Every approved generated asset should record:
- character
- asset type/name
- model
- workflow
- seed
- reference
- prompt version
- generation timestamp

## Reproducibility

Track:
- seed
- model
- prompt
- workflow
- reference
- resolution
- generation settings
- custom node versions

When a good result is found, lock it.

Do not regenerate successful assets without a reason.

## Quality Gate

Before accepting an asset, check:
- character identity
- face geometry
- eye position
- hairstyle
- clothing
- color
- lighting
- crop
- mouth anchor where applicable
- resolution
- transparency

If unrelated features changed, mark FAILED and regenerate with stronger reference-edit instructions.

## Phase Gate

PHASE 6 must pass before PHASE 7.

No lip-sync, HyperFrames, TTS, audio analysis, or video rendering work should be introduced before the image-generation milestone is locked.

## Claude Code Behavior

Before changing the system:
1. inspect
2. understand
3. propose
4. implement
5. test
6. report

Never:
- reinstall everything
- replace CUDA blindly
- install random nodes
- overwrite workflows
- delete models
- modify system-wide packages unnecessarily

Prefer project-local changes.

## Future Pipeline

Thai Script
→ TTS
→ Audio
→ Thai Phoneme
→ Viseme
→ Avatar Mouth
→ Expression
→ GSAP
→ HyperFrames
→ MP4

Keep image generation and video rendering as separate systems.
