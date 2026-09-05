# PHASE 7 — Thai Audio / Phoneme Pipeline

Status: **implemented and tested**, running ahead of the PHASE 6 image gate by explicit
instruction. See "Gate status" below — this is not the order `PLAN.md` specifies.

Deliverables, against `PLAN.md` §7:

| Step | Deliverable | Where |
|------|-------------|-------|
| 7.1 TTS | Thai TTS to WAV at a stable rate, deterministic | `scripts/audio/tts.py` |
| 7.2 Phoneme analysis | Thai G2P, engine selected and adapter-backed | `scripts/lib/thai_g2p.py` |
| 7.3 Phoneme → viseme | the PHASE 4.2 table as data | `scripts/lib/viseme_map.py` |
| 7.4 Timeline | `timeline.json` | `scripts/lib/timeline.py`, `scripts/audio/build_timeline.py` |

---

## 0. Gate status — read this first

`PLAN.md` and `CLAUDE.md` both say PHASE 6 gates PHASE 7, and the gate is **failing**:

```
$ python3 scripts/validation/lock_library.py
GATE FAILED - 8 blocking problem(s).
```

Zero of 38 image assets exist. This phase was built anyway, on explicit instruction.
What that costs, concretely:

- **Nothing here has been seen against a real mouth.** Every timing and every shape
  choice is unvalidated against an actual viseme image, because there are none.
- The Thai mapping is still **unreviewed by a Thai speaker** (PHASE 4.2). Every timeline
  carries that warning in its own metadata and every validation run prints it.
- The duration model is estimates. It has never been checked against a measured
  alignment.

None of that makes the code wrong. It makes it **unverified against the thing it exists
to drive**, and the first real test is still the PHASE 8 lip-sync pass that mapping.md
§6 describes.

---

## 1. Quick start

```bash
# What will the parser do with this text? Writes nothing.
python3 scripts/audio/build_timeline.py "สวัสดีครับ ผมชื่อนารา" --report

# Speak it and fit the timeline to the real audio.
python3 scripts/audio/build_timeline.py "สวัสดีครับ ผมชื่อนารา" --tts --name greeting

# Check the result.
python3 scripts/validation/validate_timeline.py --all
```

`--report` first, always. It is the only view of what the G2P actually did, and a wrong
parse is invisible once it has become numbers in a JSON file.

---

## 2. TTS engine selection (7.1)

PLAN 7.1 asks for a Thai-compatible engine producing WAV at a stable sample rate,
deterministic where possible. The answer differs by machine, so the engine is an
adapter chosen with `--engine`, and every timeline records which one produced its audio.

### Shipped adapters

| Engine | Thai | Deterministic | Platform | Role |
|--------|------|---------------|----------|------|
| `say` | Kanya (th_TH) | yes — byte-identical WAV across runs | macOS only | development |
| `silence` | n/a | yes | any | testing and CI |

`say` is real Thai speech, needs no install, and is verified deterministic by
`tts.py --check-determinism`. It is **not** the production engine: it is macOS-only and
the production target is the RTX 5070 box.

`silence` produces a silent WAV of the estimated length. It is not speech. It exists so
the pipeline and its tests run on any machine, and so CI never depends on a platform
binary.

### Choosing the production engine

Deferred until the target machine exists. Criteria, in the order they matter here:

1. **Runs locally.** CLAUDE.md is local-first throughout; a cloud TTS would be the
   first exception in the project.
2. **Deterministic.** The image pipeline locks a seed and expects the same bytes back.
   Audio should not be looser than that.
3. **Emits phoneme timings.** This is the pivotal one. An engine that reports its own
   aligned phonemes makes 7.2 nearly free and upgrades `timing_source` from `fitted`
   to `aligned` with no forced aligner in the stack. An engine that does not means
   adding an aligner (MFA-class, with a Thai acoustic model) — a heavy dependency and
   a non-deterministic step.
4. **Thai quality** — vowel length and tone, judged by a Thai speaker, not by a metric.
5. **VRAM.** A neural TTS shares the 12GB with FLUX. It should not be resident at the
   same time as image generation; the two pipelines stay separate (DESIGN.md).

To add an engine: write a `synthesize_*` function returning the metadata dict, register
it in `ENGINES` in `tts.py`, and record the choice in `DECISIONS.md`.

---

## 3. Thai G2P (7.2)

PLAN 7.2 asks for a Thai phoneme/forced-alignment approach to be **researched and
selected**. The selection is: an external engine when one is installed, and a built-in
rule parser as the zero-dependency fallback (ADR-021). Both go through
`thai_g2p.phonemize()`; `--g2p-engine` picks between them.

**pythainlp** is the recommended external engine when the target machine can install
it: it is local, actively maintained, and brings a real tokenizer and pronunciation
dictionary — which is exactly what the built-in parser does not have. It is not a
dependency of this repository (ADR-007), so nothing here imports it. Register it with
`thai_g2p.register_engine("pythainlp", fn)`.

### What the built-in parser does

Thai text → strip tone marks → apply karan → expand `ๆ` → score every possible
segmentation → syllables → IPA.

Tone marks go first because mapping.md §0 establishes that all five Thai tones share one
articulation. Tone cannot change a mouth shape, so dropping it early removes a large
amount of orthographic complexity for free.

Segmentation is a scored search, not greedy longest-match. The two differ on cases like
ดีครับ, where the ค can be the coda of one syllable or the head of the cluster คร in the
next, and both readings are locally legal:

```
greedy:  diːk̚ rap̚      wrong
scored:  diː  kʰrap̚     right
```

The score is only penalties — a syllable with no written vowel costs something, and
taking a coda that would split a cluster costs more. There is no per-syllable bonus,
because a positive base makes "more syllables" win by arithmetic rather than by fit.

### Its ceiling, and the escape hatch

Thai spelling underdetermines pronunciation. No rule set resolves loanwords, irregular
readings, or compounds that resyllabify — those need a dictionary. Where the rules get
it wrong, `docs/audio/thai-lexicon.json` overrides them:

```json
{ "words": { "ครับ": ["kʰrap̚"], "อร่อย": ["ʔa", "rɔːj"] } }
```

Keys are Thai surface forms with tone marks stripped; values are IPA syllables. A listed
pronunciation outranks any rule reading. The shipped file is seeded from parser errors
found while building this phase — 20 entries, not a dictionary.

**Add to it whenever `--report` shows a word coming out wrong.** That is the intended
workflow, not a workaround.

Anything the parser cannot handle at all is reported, never guessed: `coverage` and
`unparsed` are recorded in every timeline, and `build_timeline.py` exits non-zero below
95% coverage.

---

## 4. Phoneme → viseme (7.3)

`docs/thai-viseme/thai-viseme-mapping.md` (PHASE 4.2) is the prose and the reasoning.
`docs/thai-viseme/thai-viseme-map.json` is the same table as data. Code reads the JSON;
a Thai speaker reviews the markdown.

They are checked against each other by `tests/audio/test_viseme_map.py`, which parses
the markdown tables and compares every row (ADR-019). If they disagree, the review does
not apply to the animation, so the test fails. **Edit both or neither.**

Two rules from the mapping are enforced in code rather than left to the animator:

- `/h/` and `/ʔ/` have no visible articulation (§1). They map to nothing and their time
  is given to the neighbouring vowel — the time is real, so it is handed over, not
  deleted.
- A diphthong is two shapes, not one (§2). `/ia/` becomes `I` → `A` sharing the vowel's
  duration.

`TH` is not reachable from native Thai. mapping.md §5 explains why: Thai has no
interdental consonant. It is in the `loanword` section for `/θ/` and `/ð/`, and a test
asserts it never appears in the native mapping.

---

## 5. Timeline (7.4)

The shape is PLAN 7.4's — `duration` plus events of `start`, `end`, `phoneme`, `viseme` —
with the provenance fields CLAUDE.md requires of anything reproducible.

### `timing_source` — how much the numbers are worth

| Value | Means |
|-------|-------|
| `estimated` | No audio existed. Durations come from the class model; the total is a guess. |
| `fitted` | Audio existed and was measured. Estimates set the proportions and are scaled so the total matches the real file. |
| `aligned` | A forced aligner produced the times. **Nothing produces this yet.** |

The field exists so PHASE 8 can tell a measured time from a guessed one without having
to ask. Do not remove it, and do not let anything write `aligned` until something
actually aligns.

### Guarantees the validator enforces

- Events tile the duration exactly — no gaps, no overlaps. A gap is a moment where the
  mouth is undefined.
- Every viseme is in the canonical 16 (`scripts/lib/canon.py`). A shape outside the set
  names an asset that can never exist.
- No two adjacent events share a viseme — one hold is one event.
- No event is shorter than `min_viseme_duration_s` (0.060s). mapping.md §6: a viseme
  held for one frame reads as a flicker. Anything shorter is absorbed into its longer
  neighbour and **recorded in `absorbed_events`** rather than silently dropped.
- The total keeps summing to the audio length through every one of those
  transformations, because it describes audio that actually exists.
- `digest` is a stable hash over the events and inputs, excluding the timestamp. Two
  runs of the same text are recognisably the same timeline, the way two runs of the same
  seed are the same image. A hand-edited file fails it.

### What is deliberately absent

Coarticulation, blend weights, hold-versus-transition, and stress. mapping.md §6 assigns
all four to PHASE 8. This phase emits target shapes and honest times; the animation
engine decides how to move between them.

---

## 6. Duration model

`docs/audio/thai-duration-model.json` — per-class durations at a neutral speaking rate.

These are **estimates, not measurements**. Their real job is to distribute a known audio
duration across visemes in a plausible ratio; the absolute values only matter when there
is no audio at all. Thai vowel length is phonemic, so short and long vowels differ by
roughly 2:1, which is the largest single effect in the model.

Tune it by watching a real lip-sync pass in PHASE 8 and adjusting classes, not
individual phonemes.

---

## 7. Files

```
scripts/lib/thai_g2p.py            Thai text -> IPA phonemes (7.2)
scripts/lib/viseme_map.py          phoneme -> viseme (7.3)
scripts/lib/timeline.py            phones + timing -> timeline.json (7.4)
scripts/lib/audioinfo.py           WAV duration, format, hashing
scripts/audio/tts.py               Thai text -> WAV, pluggable engine (7.1)
scripts/audio/build_timeline.py    the whole pipeline, one command
scripts/validation/validate_timeline.py   timeline QC

docs/thai-viseme/thai-viseme-map.json     the 4.2 table as data
docs/audio/thai-duration-model.json       per-class duration estimates
docs/audio/thai-lexicon.json              G2P exception lexicon

metadata/timelines/                generated timelines
assets/audio/                      generated WAV (not committed)
```

---

## 8. Before PHASE 8

- [ ] **Pass the PHASE 6 gate.** Still the real prerequisite; none of this has been seen
      against a real mouth.
- [ ] Get `thai-viseme-mapping.md` reviewed by a Thai speaker, then set
      `reviewed_by_thai_speaker: true` in the JSON. Both files, or the test fails.
- [ ] Select the production TTS engine on the RTX 5070 machine and record it in
      `DECISIONS.md`.
- [ ] Decide whether a forced aligner is worth its dependency, or whether `fitted` is
      good enough. Watch a real lip-sync pass before deciding.
- [ ] Grow the lexicon from real scripts, not from invented test sentences.
