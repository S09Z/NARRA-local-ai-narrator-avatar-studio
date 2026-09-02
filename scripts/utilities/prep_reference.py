#!/usr/bin/env python3
"""Bring a candidate reference image up to ASSET_SPEC before import (PHASE 1.1).

`validate_reference.py` says yes or no. It does not fix anything, and it should not -
a validator that edits its input cannot be trusted about what it validated. This is
the other half: the small, mechanical corrections that stand between a generated
candidate and the spec, applied once and reported line by line.

What it corrects is deliberately narrow:

Near-opaque alpha. A candidate whose body sits at alpha 253 is a clean cutout, but
ASSET_SPEC 4 is checked against exact opacity, so it reports as ~30% semi-transparent
and reads like a soft matte. Snapping >=250 to 255 and <=5 to 0 removes the encode
artefact without touching the antialiased edge, which is the thing the check exists
to protect.

Resolution. Downscaled to 1024x1024 (ASSET_SPEC 1) with LANCZOS. Pillow weights RGB
by alpha when it resamples RGBA, so colour from fully transparent pixels is not dragged
into the silhouette edge - a halo manufactured by the resize is exactly what the spec
forbids, so a test pins that behaviour rather than trusting it.

What it will not do is invent an alpha channel, squash a non-square image to fit, or
touch the pixels of the character. A candidate with a genuine soft matte, a missing
cutout, or the wrong framing is a generation problem, and this tool refuses it rather
than papering over it. The output still has to pass validate_reference.py, and the
visual checklist there is still a person's job.

Usage:
    prep_reference.py assets/input/candidate.png
    prep_reference.py candidate.png --out assets/input/candidate-prepped.png
    prep_reference.py candidate.png --pad          non-square: letterbox, never squash
    prep_reference.py candidate.png --force        overwrite an existing output

Exit code 0 = written and the output passes the automated checks,
1 = refused, or written but still failing, 2 = usage error.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import imagecheck                                    # noqa: E402
from imagecheck import Report                        # noqa: E402

REPO = Path(os.environ.get("NARRA_REPO", Path(__file__).resolve().parents[2]))

TARGET_SIZE = imagecheck.REQUIRED_SIZE

# An encode that lands the body on 253 is not a matte. The window is tight on purpose:
# wide enough for lossy quantisation, far too narrow to flatten a real soft edge, which
# spreads across the whole 0-255 range rather than clustering at the ends.
OPAQUE_AT = 250
CLEAR_AT = 5

# Above this, the alpha is a genuine soft matte and snapping it would hide a real
# defect - the generation needs redoing, not correcting (ASSET_SPEC 4).
MAX_TRUE_SOFT_FRACTION = imagecheck.MAX_SEMI_TRANSPARENT_FRACTION

SUFFIX = "-prepped"


def rel(path):
    path = Path(path)
    return str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path)


def default_out(candidate):
    return candidate.with_name(f"{candidate.stem}{SUFFIX}{candidate.suffix}")


def alpha_profile(alpha):
    """How the alpha channel is distributed, in the terms the decisions are made in."""
    histogram = alpha.histogram()
    total = float(alpha.size[0] * alpha.size[1])
    return {
        "clear": sum(histogram[:CLEAR_AT + 1]) / total,
        "opaque": sum(histogram[OPAQUE_AT:]) / total,
        # The pixels a snap will not touch: a real antialiased edge, or a real matte.
        "soft": sum(histogram[CLEAR_AT + 1:OPAQUE_AT]) / total,
        # What ASSET_SPEC 4 currently measures - exact-255 opacity.
        "semi": (total - histogram[0] - histogram[255]) / total,
    }


def snap(alpha):
    """Quantisation off the ends of the range; everything between is left alone."""
    return alpha.point(
        lambda value: 255 if value >= OPAQUE_AT else (0 if value <= CLEAR_AT else value))


def pad_to_square(image, Image):
    """Letterbox onto transparent. Lossless here - the background is already empty."""
    width, height = image.size
    side = max(width, height)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(image, ((side - width) // 2, (side - height) // 2))
    return canvas


def prep(candidate, out_path, allow_pad, log):
    """Returns the prepared image, or None with the refusal already logged."""
    Image = imagecheck.load_pillow()
    if Image is None:
        log.append(("error", "Pillow is required - run: make install"))
        return None
    with Image.open(candidate) as opened:
        image = opened.convert("RGBA") if opened.mode != "RGBA" else opened.copy()
        had_icc = bool(opened.info.get("icc_profile"))
        original_mode = opened.mode

    if original_mode not in ("RGBA", "LA"):
        log.append(("refused",
                    f"mode is {original_mode}, not RGBA - there is no cutout to prepare. "
                    "The character must be matted off its generation background first "
                    "(character/reference/README.md section 2)."))
        return None
    if original_mode != "RGBA":
        log.append(("alpha", f"converted {original_mode} to RGBA"))

    # Refuse a real soft matte rather than flattening it into a fake pass. Measured
    # before any padding, which would only dilute the fraction with empty pixels.
    source_alpha = alpha_profile(image.getchannel("A"))
    if source_alpha["soft"] > MAX_TRUE_SOFT_FRACTION:
        log.append(("refused",
                    f"{source_alpha['soft']:.2%} of pixels are genuinely part-transparent "
                    f"(alpha {CLEAR_AT + 1}-{OPAQUE_AT - 1}), over the "
                    f"{MAX_TRUE_SOFT_FRACTION:.0%} limit. That is a soft matte or halo, "
                    "not an encode artefact, and snapping it would hide a real defect - "
                    "redo the cutout (ASSET_SPEC 4)."))
        return None

    width, height = image.size
    if width != height:
        if not allow_pad:
            log.append(("refused",
                        f"{width}x{height} is not square and ASSET_SPEC 2 requires 1:1. "
                        "Resizing would squash the character; re-run with --pad to "
                        "letterbox onto a transparent square canvas instead."))
            return None
        image = pad_to_square(image, Image)
        log.append(("pad", f"{width}x{height} letterboxed to "
                           f"{image.size[0]}x{image.size[1]} on transparent"))

    # Recomputed after any padding, so the reported fractions describe what was written.
    before = alpha_profile(image.getchannel("A"))
    alpha = snap(image.getchannel("A"))
    image.putalpha(alpha)
    after = alpha_profile(alpha)
    log.append(("alpha", f"snapped >={OPAQUE_AT} to 255 and <={CLEAR_AT} to 0; "
                         f"semi-transparent {before['semi']:.2%} -> {after['semi']:.2%}, "
                         f"opaque {after['opaque']:.2%}"))

    if image.size != tuple(TARGET_SIZE):
        source = image.size
        image = image.resize(tuple(TARGET_SIZE), Image.LANCZOS)
        # Resampling reintroduces near-opaque values along the edge; snap again so the
        # output holds the property the first snap established.
        image.putalpha(snap(image.getchannel("A")))
        log.append(("resize", f"{source[0]}x{source[1]} -> "
                              f"{TARGET_SIZE[0]}x{TARGET_SIZE[1]}, LANCZOS"))
    else:
        log.append(("resize", f"already {TARGET_SIZE[0]}x{TARGET_SIZE[1]}, left alone"))

    if had_icc:
        log.append(("icc", "embedded ICC profile dropped - the pipeline assumes sRGB "
                           "(ASSET_SPEC 3). Convert deliberately if the source was not sRGB."))
    else:
        log.append(("icc", "no embedded profile"))

    return image


def main():
    parser = argparse.ArgumentParser(
        description="Correct a candidate reference image to ASSET_SPEC, then re-check it.")
    parser.add_argument("candidate", type=Path, help="candidate reference image")
    parser.add_argument("--out", type=Path,
                        help=f"output path (default: <candidate>{SUFFIX}.png)")
    parser.add_argument("--pad", action="store_true",
                        help="letterbox a non-square candidate instead of refusing it")
    parser.add_argument("--force", action="store_true",
                        help="overwrite an existing output file")
    args = parser.parse_args()

    candidate = args.candidate
    if not candidate.exists():
        print(f"error: {candidate} not found", file=sys.stderr)
        return 2

    out_path = args.out or default_out(candidate)
    if out_path.resolve() == candidate.resolve():
        print("error: refusing to overwrite the candidate - the original is the record "
              "of what was generated", file=sys.stderr)
        return 2
    if out_path.exists() and not args.force:
        print(f"error: {rel(out_path)} exists - pass --force to overwrite",
              file=sys.stderr)
        return 2

    print(f"Prepping {rel(candidate)}\n")

    log = []
    image = prep(candidate, out_path, args.pad, log)
    width = max((len(name) for name, _ in log), default=0)
    for name, detail in log:
        print(f"  {name.ljust(width)}  {detail}")

    if image is None:
        print("\nREFUSED - nothing written.")
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)
    print(f"\nWrote {rel(out_path)}\n")

    report = Report()
    if imagecheck.check_header(out_path, report):
        imagecheck.check_pixels(out_path, report)
    print(report.render())

    if report.failed():
        print(f"\nFAILED - {rel(out_path)} still does not meet ASSET_SPEC. What is left "
              "is not mechanical; the generation needs redoing.")
        return 1

    print("\nAutomated checks passed. Still to do:")
    print(f"  python3 scripts/validation/validate_reference.py {rel(out_path)}")
    print("  ...then --import, once the visual checklist is confirmed by eye.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
