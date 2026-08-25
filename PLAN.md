# PLAN.md

# NARRA — Local AI Narrator Avatar Studio

## 0. Vision

NARRA is a local-first AI narrator avatar production system.

Starting point:
Reference Avatar

First milestone:
Generate a consistent library of:
- expressions
- Thai speech visemes
- narrator poses

Only after the image-generation pipeline is stable will the project implement:
Audio → Phoneme → Viseme → Animation → HyperFrames → MP4

## 1. Project Name

NARRA — Local AI Narrator Avatar Studio

Repository:
narrа-avatar-studio

## 2. Hardware

- NVIDIA RTX 5070
- 12GB VRAM
- 32GB RAM

Primary model:
FLUX.2 Klein 4B Distilled

Quality/editing:
FLUX.2 Klein 4B Base

## 3. Phases

PHASE 0 — Environment & Architecture
PHASE 1 — Reference Avatar Foundation
PHASE 2 — Prompt & Character Consistency
PHASE 3 — Expression System
PHASE 4 — Thai Viseme System
PHASE 5 — Pose & Narrator Asset Library
PHASE 6 — Asset Validation & Production Lock
PHASE 7 — Thai Audio / Phoneme Pipeline
PHASE 8 — Lip-Sync Animation Engine
PHASE 9 — HyperFrames Video Pipeline
PHASE 10 — Production Automation

---

# PHASE 0 — Environment & Architecture

## 0.1 Environment Audit
- detect GPU/VRAM
- detect CUDA/PyTorch
- detect Python
- detect ComfyUI
- detect Manager
- detect custom nodes
- detect FLUX models

Acceptance:
- ComfyUI launches
- Klein 4B loads
- test image succeeds
- VRAM usage is practical

## 0.2 Model Installation
Install:
- FLUX.2 Klein 4B Distilled
- FLUX.2 Klein 4B Base

Use FP8 where appropriate.

## 0.3 Baseline Workflows
Create:
- workflows/00_text_to_image.json
- workflows/01_reference_edit.json
- workflows/02_image_edit.json

## 0.4 Project Structure
Create:
- CLAUDE.md
- PLAN.md
- README.md
- DESIGN.md
- MEMORY.md
- character/
- prompts/
- workflows/
- scripts/
- metadata/
- docs/
- tests/

---

# PHASE 1 — Reference Avatar Foundation

## 1.1 Import Reference
Store canonical reference at:
character/reference/master.png

## 1.2 Character Bible
Create:
character/bible/character-bible.md

Document:
- visual identity
- face
- hair
- eyes
- skin
- clothing
- accessories
- style
- lighting
- camera
- personality
- narrator role

## 1.3 Visual Specification
Create:
character/bible/visual-spec.md

## 1.4 Baseline Tests
Generate:
- neutral
- slight smile
- speaking

Acceptance:
character remains recognizable and visually consistent.

### PHASE 1 GATE
Do not continue if identity is unstable.

---

# PHASE 2 — Prompt & Character Consistency

## 2.1 Master Prompt
Create:
prompts/master/master-character.md

## 2.2 Prompt Variables
Support:
- character
- expression
- viseme
- pose
- camera
- lighting
- scene

## 2.3 Versioning
Use prompt versions such as:
master-character-v1.0

## 2.4 Deterministic Seeds
Expression: 10000–10999
Viseme: 20000–20999
Pose: 30000–30999

## 2.5 Reference Editing Tests
Test:
- change only hair
- change only eyes
- change only mouth
- change only expression

Acceptance:
unrequested properties remain stable.

---

# PHASE 3 — Expression System

## 3.1 Canonical Set

Generate:
1. neutral
2. friendly
3. happy
4. excited
5. serious
6. concerned
7. surprised
8. confused
9. thinking
10. explaining
11. proud
12. embarrassed

## 3.2 Dedicated Prompts
Create one prompt per expression.

## 3.3 Generation
Prefer reference editing.

## 3.4 QC
Check identity, eyes, eyebrows, face, hair, clothing, expression.

## 3.5 Lock
Store approved assets in:
character/expressions/

---

# PHASE 4 — Thai Viseme System

## 4.1 Canonical Set

REST
A
I
U
E
O
AE
AO
MBP
FV
TH
KG
S
SH
L
N

## 4.2 Thai Mapping
Create:
docs/thai-viseme-mapping.md

Map Thai phonetic groups to visual mouth shapes.

## 4.3 Mouth Anchor
Define:
- mouth anchor X/Y
- mouth width
- mouth height

All visemes must align.

## 4.4 Generation
reference → mouth mask → FLUX.2 edit → viseme

Prompt must say:
"Change only the mouth."

## 4.5 QC
Check:
- same face
- same eye position
- same hair
- same clothing
- same camera
- same lighting
- same mouth anchor

## 4.6 Lock
Store approved assets in:
character/visemes/

---

# PHASE 5 — Pose & Narrator Asset Library

## 5.1 Pose Set
Generate:
- neutral
- explaining
- pointing-left
- pointing-right
- presenting
- surprised
- thinking
- concerned
- confident
- excited

## 5.2 Camera Set
Generate:
- close-up
- medium
- upper-body
- three-quarter

## 5.3 Narrator Compositions
Create reusable states:
- talking
- explaining
- presenting
- reaction
- emphasis

---

# PHASE 6 — Asset Validation & Production Lock

This is the hard gate before video.

## 6.1 Completeness
Required:
- 12 expressions
- 16 visemes
- 10 poses

## 6.2 Contact Sheet
Create side-by-side review sheets.

## 6.3 Resolution Lock
Default:
1024x1024

Upscale only approved master assets.

## 6.4 Metadata Lock
Record:
- model
- seed
- prompt version
- workflow
- reference
- generation timestamp

## 6.5 Production Baseline
Create:
docs/production-baseline.md

Record:
- model versions
- ComfyUI version
- custom nodes
- workflow versions
- prompt versions
- seeds
- generation settings

### IMAGE PIPELINE GATE

PHASE 6 must pass before PHASE 7.

Success:

Reference
→ Expressions
→ Visemes
→ Poses
→ QC
→ LOCKED

No lip-sync development before this point.

---

# PHASE 7 — Thai Audio / Phoneme Pipeline

## 7.1 TTS
Select a Thai-compatible TTS engine.

Output:
- WAV
- stable sample rate
- deterministic output where possible

## 7.2 Thai Phoneme Analysis
Research and select a Thai-compatible phoneme/forced-alignment approach.

## 7.3 Phoneme → Viseme
Create mapping.

## 7.4 Timeline
Output:
timeline.json

Example:
{
  "duration": 4.2,
  "events": [
    {
      "start": 0.0,
      "end": 0.12,
      "phoneme": "a",
      "viseme": "A"
    }
  ]
}

---

# PHASE 8 — Lip-Sync Animation Engine

## 8.1 Mouth Switching
REST → VISEME → REST

## 8.2 Coarticulation
Smooth transitions using previous/current/next visemes.

## 8.3 Expression Layer
Expression and viseme remain independent.

Example:
happy + A
happy + I
happy + O

## 8.4 Secondary Animation
After basic lip-sync:
- blinking
- breathing
- subtle head movement
- eyebrow movement

---

# PHASE 9 — HyperFrames Video Pipeline

Use HyperFrames as:
- animation compositor
- timeline engine
- subtitle renderer
- camera animation
- final video renderer

Pipeline:

Avatar
+ Audio
+ Viseme Timeline
+ Expression Timeline
+ Subtitles
+ Camera
+ B-roll
→ HyperFrames
→ MP4

Use GSAP for:
- mouth transitions
- head movement
- camera
- text animation
- expression transitions

Support Thai Unicode and Thai fonts.

---

# PHASE 10 — Production Automation

## 10.1 CLI
Target commands:
- narra generate-avatar
- narra generate-expressions
- narra generate-visemes
- narra generate-poses
- narra generate-video

## 10.2 Batch
Support episode-001, episode-002, etc.

## 10.3 Caching
Cache:
- images
- TTS
- phoneme timeline
- viseme timeline
- rendered scenes

Do not regenerate unchanged assets.

---

# Priority

P0:
- environment
- reference
- character consistency
- expressions
- Thai visemes

P1:
- poses
- QC
- production lock

P2:
- Thai audio
- phoneme
- lip-sync

P3:
- HyperFrames
- video automation

---

# Explicit Non-Goals Before PHASE 6

Do NOT:
- build lip-sync
- build HyperFrames integration
- build video rendering
- train LoRA
- build TTS
- build audio analysis

The project must first solve:

"Can we reliably generate the correct avatar image?"

---

# Definition of Success

One reference avatar
→ 12 expressions
→ 16 Thai visemes
→ 10 poses
→ visually consistent
→ reproducible
→ production locked

Only then proceed to video.
