---
name: push-draft-pr
description: Use when implementing the next milestone from PLAN.md and shipping it for review - reads the plan, identifies the current milestone, implements it, validates against acceptance criteria, commits, pushes a feature branch, and opens a Draft PR
---

# push-draft-pr

> **STATUS: PLACEHOLDER — NOT IMPLEMENTED.**
> This is a scaffold created during project structure initialization.
> Every section below is a TODO. Do not rely on this skill until it is written.

## Purpose

Take the current milestone from `PLAN.md` through implementation to a Draft PR,
in one reviewable increment.

## Safety Rules (binding, even in placeholder form)

- NEVER force push. No `--force`, no `--force-with-lease`.
- NEVER commit directly to `main` or `master`. Always work on a feature branch.
- NEVER discard or stash unrelated user changes. Preserve the working tree.
- NEVER open a non-draft PR from this skill.
- One milestone per PR. Do not bundle unrelated work.
- Respect the PHASE 6 gate in `PLAN.md` — no lip-sync, TTS, HyperFrames, or video work
  before the image pipeline is production-locked.

## Workflow

### 1. Read the plan
TODO — parse `PLAN.md`; locate the phase/milestone structure.

### 2. Identify the current milestone
TODO — determine the first milestone that is not complete. Define how completion is
detected (cross-reference `MEMORY.md` → Current Status). Confirm with the user before
implementing if ambiguous.

### 3. Check acceptance criteria
TODO — extract the milestone's acceptance criteria and phase gate. Verify the previous
phase gate passed before starting. Abort if a gate is unmet.

### 4. Implement
TODO — implement only the identified milestone. Define scope boundaries and what to do
when the milestone is larger than one PR.

### 5. Validate
TODO — define the validation step per milestone type (docs, prompts, workflows, assets).
Cross-check generated assets against `ASSET_SPEC.md` quality criteria where applicable.
Never claim success without running the check and reading its output.

### 6. Commit
TODO — create a focused commit containing only files related to this milestone.
Define the commit message convention. Stage explicitly; never `git add -A` blindly.

### 7. Push a feature branch
TODO — define the branch naming convention (e.g. `phase-<n>/<milestone-slug>`).
Push with upstream tracking. No force push.

### 8. Open a Draft PR
TODO — create the PR with `gh pr create --draft`. Define the PR body template:
milestone, acceptance criteria checklist, validation evidence, what is out of scope.

## Preconditions

TODO — confirm before running:
- [ ] Repository is a git repository with a remote configured
- [ ] `gh` CLI is authenticated
- [ ] Working tree state is understood (unrelated changes identified and preserved)
- [ ] Not currently on `main` / `master` when committing

## Notes

- The repository is not yet git-initialized. This skill cannot run until it is.
- Related docs: `PLAN.md` (milestones), `CLAUDE.md` (project rules and quality gates),
  `DECISIONS.md` (record any architectural decision made while implementing).
