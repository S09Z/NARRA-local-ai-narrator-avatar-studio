---
id: master-character
version: 1.0
kind: master
---

<!--
PHASE 2.1 — Master Prompt.

Status: UNFILLED. Every <...> slot is filled from character/bible/character-bible.md,
which is itself filled from the approved reference image. Do not invent values here —
the bible is the single place the character is described, and this file is its
prompt-shaped projection.

Slot -> bible section:
  CHARACTER  -> §1 Identity, §2 Face, §3 Eyes, §4 Eyebrows, §5 Hair, §6 Skin,
                §7 Clothing, §8 Accessories
  STYLE      -> §9 Art Style
  LIGHTING   -> §10 Lighting
  CAMERA     -> §11 Camera and Framing
  OUTPUT     -> ASSET_SPEC.md §1-§4

This file is descriptive only. It never contains a TASK (PROMPT_GUIDE.md §2).
Compiling any asset includes this file verbatim, so a MAJOR bump here invalidates
every approved asset in character/.
-->

## CHARACTER

<one-line identity sentence: bible §1>
face: <face shape, proportions, distinguishing features: bible §2>
eyes: <shape, color, size, spacing: bible §3>
eyebrows: <shape, thickness, arch, color: bible §4>
hair: <cut, length, part, color, texture, silhouette: bible §5>
skin: <tone and undertone: bible §6>
clothing: <garment, neckline, collar, colors, pattern: bible §7>
accessories: <list, or the literal word "none": bible §8>

## STYLE

<art style family; line work and weight; shading model; color treatment: bible §9>

## LIGHTING

<key direction and softness; fill; rim; shadow side: bible §10>

## CAMERA

<default framing, head angle, shoulder line, lens character: bible §11>

## OUTPUT

1024x1024, square, flat uniform background, character centered with the full head in frame.
