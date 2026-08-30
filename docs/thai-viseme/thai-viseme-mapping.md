# Thai Phoneme → Viseme Mapping — PHASE 4.2

Maps Thai phonetic groups to the 16 visual visemes in `ASSET_SPEC.md` §7.

`PLAN.md` §4.2 names this file `docs/thai-viseme-mapping.md`; `ASSET_SPEC.md` §7 says the
mapping lives in `docs/thai-viseme/`. It is here, in the directory the repository actually
has.

---

## 0. Scope and honesty about it

This is a **visual animation approximation**, not a phonological model
(`CLAUDE.md`, `ASSET_SPEC.md` §7). Two consequences:

1. Phonemes that look the same from the front share a viseme even when they are
   phonologically distinct. /t/ and /d/ differ only in voicing, which is invisible.
2. Phonemes with no visible articulation — /h/, /ʔ/ — have no viseme of their own and
   take the shape of the vowel around them.

**This mapping has not been reviewed by a Thai speaker.** It is derived from the standard
description of Thai phonology and from what is visible on the front of a face; it is a
defensible starting point for animation, not an authority. The places most likely to need
correction by a native speaker are marked ⚠ below. Treat the first lip-sync pass in
PHASE 8 as the real test, and revise this file from what is observed there.

Tones do not affect mouth shape. Thai has five tones; all five are produced with the same
articulation, so tone is ignored here entirely. It matters for duration in PHASE 8, not
for viseme selection.

---

## 1. Initial consonants

| Thai | IPA | Viseme | Note |
|------|-----|--------|------|
| ก | /k/ | `KG` | |
| ข ฃ ค ฅ ฆ | /kʰ/ | `KG` | aspiration is not visible |
| ง | /ŋ/ | `KG` | |
| จ | /tɕ/ | `SH` | alveolo-palatal; lips protrude |
| ฉ ช ฌ | /tɕʰ/ | `SH` | |
| ซ ศ ษ ส | /s/ | `S` | |
| ฎ ด | /d/ | `N` | |
| ฏ ต | /t/ | `N` | voicing is not visible, so same as /d/ |
| ฐ ฑ ฒ ถ ท ธ | /tʰ/ | `N` | ⚠ see §5 on `TH` |
| ณ น | /n/ | `N` | |
| บ | /b/ | `MBP` | |
| ป | /p/ | `MBP` | |
| ผ พ ภ | /pʰ/ | `MBP` | |
| ฝ ฟ | /f/ | `FV` | Thai has no /v/ |
| ม | /m/ | `MBP` | |
| ย ญ | /j/ | `I` | glide; takes a spread shape |
| ร | /r/ | `L` | commonly realised as [l] in speech |
| ล ฬ | /l/ | `L` | |
| ว | /w/ | `U` | glide; takes a rounded shape |
| ห ฮ | /h/ | *(none)* | no visible articulation — hold the following vowel |
| อ | /ʔ/ | *(none)* | zero initial — hold the following vowel |

The three bilabials /b p pʰ/ and the nasal /m/ all collapse to `MBP`. This is correct and
expected: they are indistinguishable from the front, which is exactly why `MBP` must be
distinguishable from `REST` (`ASSET_SPEC.md` §7). If it is not, every bilabial in Thai
reads as a closed idle mouth and the lip-sync looks dead.

---

## 2. Vowels

Thai contrasts short and long vowels. Length changes duration, not shape, so both map to
the same viseme and the distinction is carried by frame count in PHASE 8.

| Thai | IPA | Viseme | Note |
|------|-----|--------|------|
| อะ อา | /a aː/ | `A` | maximum jaw drop |
| แอะ แอ | /ɛ ɛː/ | `AE` | flat and wide |
| เอะ เอ | /e eː/ | `E` | |
| อิ อี | /i iː/ | `I` | |
| อึ อื | /ɨ ɨː/ | `I` | close central unrounded — reads as `I` from the front |
| อุ อู | /u uː/ | `U` | tight rounding |
| โอะ โอ | /o oː/ | `O` | |
| เอาะ ออ | /ɔ ɔː/ | `AO` | |
| เออะ เออ | /ə əː/ | `E` | ⚠ mid central; `E` is the nearest neutral shape |

### Diphthongs

Thai has three true diphthongs. Each is animated as a transition between two visemes, not
as a single shape.

| Thai | IPA | Visemes | Note |
|------|-----|---------|------|
| เอีย | /ia/ | `I` → `A` | |
| เอือ | /ɨa/ | `I` → `A` | ⚠ starts less spread than เอีย; same visual path |
| อัว | /ua/ | `U` → `A` | |

### Vowel + glide sequences

Written with vowel symbols but animated as a vowel moving into a glide shape.

| Thai | IPA | Visemes |
|------|-----|---------|
| ไอ ใอ อัย | /aj/ | `A` → `I` |
| เอา | /aw/ | `A` → `U` |
| อาย | /aːj/ | `A` → `I` |
| อาว | /aːw/ | `A` → `U` |

---

## 3. Final consonants

Thai allows only eight finals. Stops are **unreleased** — the mouth closes and holds; it
does not pop open again. Animating a release frame is the most common way to make Thai
lip-sync look foreign.

| Thai final | IPA | Viseme | Note |
|------------|-----|--------|------|
| -บ -ป -พ -ฟ -ภ | /p̚/ | `MBP` | hold the closure |
| -ด -ต -ถ -ท -ธ -ส -ช -จ -ศ -ษ -ซ | /t̚/ | `N` | hold; tongue at the ridge |
| -ก -ข -ค -ฆ | /k̚/ | `KG` | hold; shallow |
| -ม | /m/ | `MBP` | |
| -น -ญ -ณ -ร -ล -ฬ | /n/ | `N` | |
| -ง | /ŋ/ | `KG` | |
| -ว | /w/ | `U` | |
| -ย | /j/ | `I` | |

Many written finals neutralise: ส, ช, จ, ศ, ษ, ซ all become /t̚/ in final position, so
they all animate as `N` regardless of spelling. Drive the mapping from **pronunciation,
not orthography** — a grapheme-based mapping will be wrong here.

---

## 4. Consonant clusters

Thai initial clusters are /kr kl kw kʰr kʰl kʰw pr pl pʰr pʰl tr/. Visually the **first**
element determines the shape, because the cluster is produced fast and the second element
is a liquid or glide that blends into the vowel.

| Cluster | Viseme | Note |
|---------|--------|------|
| กร กล | `KG` | |
| กว ขว คว | `KG` → `U` | the /w/ rounding is visible; give it a frame |
| ปร ปล พร พล ผล | `MBP` | the closure dominates |
| ตร | `N` | |

Only /w/ clusters get a second frame. /r/ and /l/ in a cluster are too brief to read.

---

## 5. Coverage of the 16-viseme set

| Viseme | Thai load | Note |
|--------|-----------|------|
| `REST` | high | silence, pauses, sentence ends |
| `A` | very high | /a aː/ is the most common Thai vowel |
| `I` | high | /i iː ɨ ɨː j/ and diphthong onsets |
| `U` | high | /u uː w/ |
| `E` | high | /e eː ə əː/ |
| `O` | medium | /o oː/ |
| `AE` | medium | /ɛ ɛː/ |
| `AO` | medium | /ɔ ɔː/ |
| `MBP` | very high | /b p pʰ m/ and final /p̚/ all collapse here |
| `FV` | low | /f/ only |
| `TH` | **near zero** | ⚠ see below |
| `KG` | high | /k kʰ ŋ/ and final /k̚/ |
| `S` | medium | /s/ |
| `SH` | medium | /tɕ tɕʰ/ |
| `L` | medium | /l r/ |
| `N` | very high | /t d tʰ n/ and final /t̚/ |

### ⚠ `TH` has no native Thai phoneme

The `TH` viseme is a tongue tip visible between the teeth — an interdental. **Thai has no
interdental consonant.** ธ and ท are /tʰ/, an aspirated alveolar stop; the tongue is at the
ridge behind the teeth, not between them. They are mapped to `N` above.

`TH` is retained in the set because `CLAUDE.md` fixes the 16 and because it is needed for:

- English loanwords in Thai content
- code-switched English, which is common in Thai narration
- emphasised or hyper-articulated alveolar stops, where the tongue does come forward

It is generated and QC'd like the other fifteen. Expect it to be idle in most Thai
sentences. That is a property of the set, not a defect in the asset — but it does mean
`TH` is the lowest-value asset to spend regeneration effort on if time is short.

---

## 6. What PHASE 8 consumes

This file is a lookup table, not an animation algorithm. The animation engine
(PHASE 8, blocked by `DECISIONS.md` → ADR-001) additionally needs:

- **Coarticulation** — a viseme is influenced by its neighbours; /k/ before /u/ is already
  rounding. This table gives target shapes, not blend weights.
- **Timing** — vowel length, tone-driven duration, and syllable stress.
- **Hold vs transition** — unreleased finals hold; diphthongs transition.
- **Minimum duration** — a viseme held for one frame reads as a flicker.

None of that is in scope now, and no work on it may begin before the PHASE 6 gate.
The mapping is recorded at PHASE 4 because it is what decides *which sixteen shapes are
worth generating*, and that decision has to be made before the assets are made.
