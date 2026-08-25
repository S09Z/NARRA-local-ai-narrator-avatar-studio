# TROUBLESHOOTING.md

# NARRA — Troubleshooting

Diagnostic guide for the local FLUX.2 + ComfyUI pipeline on RTX 5070 12GB.

Rule before any fix: **inspect → understand → propose → implement → test → report**.
Never reinstall the environment, replace CUDA, or delete models as a first response.

---

## 1. ComfyUI Issues

### ComfyUI will not start
1. Read the full traceback — the last line is rarely the cause.
2. Confirm the virtual environment is the one ComfyUI was installed into.
3. Confirm no other process holds the port (default 8188).
4. Start with custom nodes disabled to isolate node-pack failures (§4).

### Web UI loads but the graph is empty or nodes are red
- Red nodes = the node type is not installed or failed to import. Check the startup log
  for `IMPORT FAILED`; the failing pack is named there.
- An empty canvas after loading a workflow usually means the JSON is from an incompatible
  ComfyUI/frontend version. Check `workflows/` for a matching version note.

### Queue accepts a prompt but nothing happens
- Check the console, not the browser. Execution errors surface server-side.
- A silently stalled queue is usually a model still loading from disk on first use.
- Confirm the browser tab is connected (websocket drops leave the UI looking idle).

### Workflow ran but produced no file
- Check the SaveImage node's output directory and prefix.
- ComfyUI writes to its own `output/` directory, which is git-ignored here. Approved
  assets are copied into `character/` deliberately, not written there directly.

---

## 2. VRAM Issues

Target: RTX 5070, 12GB. Klein 4B at FP8 should fit without `--lowvram`.

### CUDA out of memory
Work through in order — stop at the first that resolves it:
1. Confirm batch size is 1.
2. Confirm resolution is 1024x1024 (not 1536+ during iteration).
3. Confirm only one model is loaded — duplicate loader nodes load twice.
4. Remove unnecessary ControlNet / LoRA stacks from the graph.
5. Confirm FP8 weights are actually in use, not FP16.
6. Free VRAM held by other processes (browsers with hardware acceleration, other
   inference servers, a second ComfyUI instance).
7. Only then consider offload flags — and record it as a temporary workaround, not a default.

`--lowvram` is not a default. If it becomes necessary at 1024x1024 with Klein 4B,
something else is wrong; find that instead.

### VRAM stays occupied after generation
- Expected: ComfyUI caches the model deliberately to avoid reloading. This is desirable.
- To reclaim it, unload models from the ComfyUI menu rather than restarting.

### Generation is very slow but does not OOM
- Usually system-RAM offload: the model spilled to host memory. Check whether VRAM is
  near capacity and reduce the graph, not the step count.
- Confirm the text encoder is not being reloaded per generation.

### System RAM exhaustion (32GB)
- Text encoder + checkpoint + VAE loaded simultaneously plus offload can approach the limit.
- Close other heavy applications before long batch runs.
- Sequential generation, not parallel; the project does not run concurrent generations.

---

## 3. Model Loading Issues

### Model not found in the loader dropdown
1. Confirm the file is in the correct subdirectory (`checkpoints/`, `vae/`, `lora/`,
   `text_encoders/`, `controlnet/`).
2. Confirm ComfyUI's model path configuration points at this project's `models/`
   (via `extra_model_paths.yaml`, which is git-ignored and machine-local).
3. Refresh the node list in the UI — new files are not hot-detected reliably.
4. Confirm the file extension is supported (`.safetensors` preferred).

### Model fails to load / errors on load
- Verify the download completed: check the file size and hash against the source.
  A truncated download is the most common cause.
- Confirm the file is the expected variant (Base vs Distilled, FP8 vs FP16). They are
  not interchangeable in the workflows.
- Confirm the text encoder and VAE match the checkpoint family. Mismatched encoders
  produce either an immediate error or silent garbage output.

### Output is noise, black, or heavily distorted
- Wrong or missing VAE — the usual cause of black or noise output.
- Wrong text encoder pairing — the usual cause of prompt-ignoring output.
- CFG far outside the model's working range for FLUX-class models.
- Distilled model run with settings intended for the Base model (or vice versa).

### Model loads but output ignores the prompt
- Confirm the prompt is reaching the sampler (a disconnected conditioning link is silent).
- Confirm the correct text encoder is loaded.
- Distilled models are less steerable than Base — use Base for reference-edit work.

---

## 4. Custom Node Issues

Project policy: native nodes only unless justified and version-pinned (`DECISIONS.md` → ADR-005).

### A node pack fails to import
1. Read the startup log for the specific `IMPORT FAILED` entry and its exception.
2. Most failures are a missing Python dependency or a version conflict with ComfyUI core.
3. Check the pack's pinned version against the installed ComfyUI version.
4. If it cannot be resolved quickly, remove the pack. It was optional by policy.

### Everything broke after installing a node pack
- Disable the newly added pack first and confirm the baseline works again.
- Node packs that pin conflicting versions of shared dependencies can break unrelated packs.
- Reinstalling ComfyUI is not the fix; identify the pack.

### A workflow needs a node that is not installed
- Do not install it reflexively. First check whether native nodes can express the same graph.
- If it is genuinely needed: justify it, record the repository and version in
  `docs/operations/`, verify compatibility, then install.

### After a ComfyUI update, saved workflows fail
- Node signatures change between versions. Workflow JSON in `workflows/` records the
  ComfyUI version it was authored against.
- Prefer pinning ComfyUI during an active generation phase. Upgrading mid-phase
  invalidates reproducibility for assets already locked.

---

## 5. Generation Consistency Issues

This is the project's core failure mode. Consistency problems are prompt and method
problems far more often than model problems.

### Character identity drifts between assets
1. Confirm reference editing is in use, not text-to-image regeneration (ADR-003).
2. Confirm the edit starts from `character/reference/`, not from a previously derived asset.
   Chained edits compound drift.
3. Strengthen the PRESERVATION block — name the preserved features explicitly.
4. Lower the edit/denoise strength.
5. Confirm the master prompt version is identical across the set.

### Features changed that were not requested
- The prompt asked for too much. One TASK per generation.
- Add the specific drift to the negative prompt (identity group) — but fix the positive
  prompt first.
- Mark the asset FAILED. Do not accept "close enough"; it compounds across the library.

### Visemes do not align — the mouth moves between frames
- Measure the mouth anchor on each asset and compare against the reference tolerance
  (`ASSET_SPEC.md` §9: ≤0.5% of image width).
- Head position drift, not mouth drift, is the usual cause — the whole face shifted.
- Constrain the edit region more tightly and reduce edit strength.

### MBP looks identical to REST
- REST is a *relaxed* closed mouth; MBP is *actively pressed* lips with visible lip
  compression and slight tension in the surrounding area.
- Describe the compression explicitly. If they still match, both fail QC.

### Expression is not readable
- Check at 256px in a contact sheet. Narrator expressions must read at thumbnail size.
- Weak expressions come from emotion words without muscle-level geometry
  (`PROMPT_GUIDE.md` §5).

### The same seed produces different results
- Any change to model, precision, sampler, scheduler, steps, CFG, resolution, ComfyUI
  version, or custom node versions changes the output for a fixed seed.
- Compare the full metadata record, not just the seed. This is exactly why
  `ASSET_SPEC.md` §11 requires the complete environment record.

### A previously good asset cannot be reproduced
- Reproduce from the metadata sidecar, field by field.
- If reproduction still fails, an environment variable outside the record changed —
  document the gap in `docs/operations/` and add the missing field to the metadata schema.

---

## 6. Escalation

Before concluding that the environment is broken:

- [ ] Reproduced the failure at least twice
- [ ] Read the full server-side traceback
- [ ] Isolated custom nodes
- [ ] Confirmed model files are complete and correctly paired
- [ ] Confirmed the failure does not occur with a minimal native workflow
- [ ] Recorded findings in `docs/operations/`

Only after all of the above is a broader environment change worth considering — and it
is proposed and recorded first, never applied silently.
