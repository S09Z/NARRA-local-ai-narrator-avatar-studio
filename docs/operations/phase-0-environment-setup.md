# PHASE 0 Environment Setup Runbook

Status: **NOT RUN** — no GPU environment exists yet (PLAN §0, MEMORY.md "Current Status")
Gate: none automated yet; acceptance criteria are listed in PLAN.md §0.1
Target machine: NVIDIA RTX 5070, 12GB VRAM, 32GB RAM — **not this machine** (Apple M3,
no NVIDIA GPU, no CUDA). Every step below must run on the RTX 5070 box.

---

## 0. Why this exists

Every phase from 1 through 6 is scaffolding — prompts, validators, docs — waiting on two
inputs: a working image-generation environment and the canonical reference image. This
runbook covers the first input. It produces nothing that PLAN's "Explicit Non-Goals
Before PHASE 6" forbids: no TTS, no audio, no lip-sync, no video. It is pure environment
setup for the image pipeline PLAN already scopes as P0.

---

## 1. Environment audit (PLAN 0.1)

Run on the RTX 5070 machine and record the output:

```bash
# GPU / driver
nvidia-smi

# CUDA toolkit visible to PyTorch
python3 -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"

# Python
python3 --version

# Existing ComfyUI / Manager / custom nodes
ls ~/ComfyUI 2>/dev/null || echo "ComfyUI not found"
ls ~/ComfyUI/custom_nodes 2>/dev/null

# Existing FLUX models
find ~/ComfyUI/models -iname "*flux*klein*" 2>/dev/null
```

Checklist:
- [ ] GPU detected, VRAM reads ~12GB
- [ ] CUDA + PyTorch installed and `torch.cuda.is_available()` is `True`
- [ ] Python 3.10+ available
- [ ] Record driver version, CUDA version, PyTorch version, OS build in this file's
      "Recorded audit" section below once run

---

## 2. ComfyUI + Manager install

Per CLAUDE.md's ComfyUI Policy: native nodes first, ComfyUI Manager required, no other
custom node installed without justification, compatibility check, and a recorded
repository/version.

```bash
git clone https://github.com/comfyanonymous/ComfyUI.git ~/ComfyUI
cd ~/ComfyUI
pip install -r requirements.txt

git clone https://github.com/ltdrdata/ComfyUI-Manager.git custom_nodes/ComfyUI-Manager
```

Do not install `rgthree-comfy`, `KJNodes`, or `Impact Pack` yet — CLAUDE.md marks these
"recommended only when justified." Add them individually, later, only if a specific
workflow step in `workflows/` needs one, and record the justification + version here.

---

## 3. Model installation (PLAN 0.2)

Required:
- FLUX.2 Klein 4B Distilled → default model, used for all library generation
- FLUX.2 Klein 4B Base → quality/editing model, used for reference edits

Place checkpoints under this repo's `models/checkpoints/` (already scaffolded, currently
empty) or symlink from ComfyUI's own `models/checkpoints/` — pick one and be consistent,
since `docs/production-baseline.md` will record the path.

Use FP8 where appropriate (CLAUDE.md Performance) to stay inside 12GB VRAM. Do not add
LoRA or ControlNet stacks by default (CLAUDE.md: avoid unnecessary stacks).

---

## 4. Baseline workflow smoke test (PLAN 0.1 acceptance)

1. Launch ComfyUI: `python3 main.py` from `~/ComfyUI`
2. Load Klein 4B Distilled, generate one 1024x1024 test image, batch size 1
3. Confirm:
   - [ ] ComfyUI launches without error
   - [ ] Klein 4B loads
   - [ ] Test image generates successfully
   - [ ] VRAM usage stays practical (well under 12GB, no OOM, no `--lowvram` needed)

Do not proceed to PHASE 0.3/0.4 (baseline workflow JSON, project structure) or PHASE 1
(reference import) until all four boxes are checked.

---

## 5. Recorded audit

Fill in once step 1 has actually been run on the RTX 5070 machine:

| Field | Value |
|---|---|
| Date | |
| GPU / driver version | |
| CUDA version | |
| PyTorch version | |
| Python version | |
| ComfyUI commit | |
| ComfyUI-Manager commit | |
| FLUX.2 Klein 4B Distilled location | |
| FLUX.2 Klein 4B Base location | |
| Test image VRAM peak | |

---

## 6. Next step

Once this runbook's checklists are all checked: import the canonical reference image
(`scripts/validation/validate_reference.py <file> --import`) to unblock PHASE 1. See
`MEMORY.md` → "Two inputs unblock the rest of Phase 1."
