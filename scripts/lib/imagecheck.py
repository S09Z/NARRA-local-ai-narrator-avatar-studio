"""Shared image checks against ASSET_SPEC.md sections 1-4.

Imported by scripts/validation/validate_reference.py and validate_asset.py, so the
spec's pixel rules exist once. A second copy would drift the moment one validator
was updated and the other was not.

Pillow is used for pixel-level checks. Without it the header checks still run from
the standard library and the pixel checks report SKIP rather than PASS - a missing
dependency must never look like a pass.
"""

import hashlib
import struct

# ASSET_SPEC.md sections 1-4
REQUIRED_SIZE = (1024, 1024)
REQUIRED_MODE = "RGBA"
REQUIRED_BIT_DEPTH = 8
MAX_SEMI_TRANSPARENT_FRACTION = 0.06   # antialiased silhouette edge only
MIN_OPAQUE_FRACTION = 0.10             # a character occupies a real part of the frame
MAX_OPAQUE_FRACTION = 0.95             # ...but is not a full-bleed background

PASS, FAIL, WARN, SKIP = "PASS", "FAIL", "WARN", "SKIP"

PNG_COLOR_TYPES = {0: "L", 2: "RGB", 3: "P", 4: "LA", 6: "RGBA"}


class Report:
    """Accumulates check results and decides the outcome."""

    def __init__(self):
        self.rows = []

    def add(self, level, name, detail=""):
        self.rows.append((level, name, detail))

    def failed(self):
        return any(level == FAIL for level, _, _ in self.rows)

    def counts(self):
        tally = {}
        for level, _, _ in self.rows:
            tally[level] = tally.get(level, 0) + 1
        return tally

    def render(self):
        if not self.rows:
            return "  (no checks run)"
        width = max(len(name) for _, name, _ in self.rows)
        lines = []
        for level, name, detail in self.rows:
            line = f"  [{level}] {name.ljust(width)}"
            if detail:
                line += f"  {detail}"
            lines.append(line)
        return "\n".join(lines)


def read_png_header(path):
    """Return (width, height, bit_depth, mode) from the IHDR chunk, stdlib only."""
    with path.open("rb") as fh:
        if fh.read(8) != b"\x89PNG\r\n\x1a\n":
            return None
        length, chunk = struct.unpack(">I4s", fh.read(8))
        if chunk != b"IHDR" or length != 13:
            return None
        width, height, bit_depth, color_type = struct.unpack(">IIBB", fh.read(10))
    return width, height, bit_depth, PNG_COLOR_TYPES.get(color_type, f"?{color_type}")


def load_pillow():
    try:
        from PIL import Image
        return Image
    except ImportError:
        return None


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check_header(path, report, prefix=""):
    """Resolution, aspect, format, bit depth, color mode. Returns the header or None."""
    header = read_png_header(path)
    if header is None:
        report.add(FAIL, prefix + "format/png", "not a PNG file (ASSET_SPEC 3)")
        return None

    width, height, bit_depth, mode = header
    report.add(PASS, prefix + "format/png", "PNG signature and IHDR present")

    if (width, height) == REQUIRED_SIZE:
        report.add(PASS, prefix + "resolution", f"{width}x{height}")
    else:
        report.add(FAIL, prefix + "resolution",
                   f"{width}x{height}, required {REQUIRED_SIZE[0]}x{REQUIRED_SIZE[1]} "
                   "(ASSET_SPEC 1)")

    if width == height:
        report.add(PASS, prefix + "aspect-ratio", "1:1")
    else:
        report.add(FAIL, prefix + "aspect-ratio", f"{width}:{height}, required 1:1 "
                                                  "(ASSET_SPEC 2)")

    if bit_depth == REQUIRED_BIT_DEPTH:
        report.add(PASS, prefix + "bit-depth", "8 bits per channel")
    else:
        report.add(FAIL, prefix + "bit-depth", f"{bit_depth}, required 8 (ASSET_SPEC 3)")

    if mode == REQUIRED_MODE:
        report.add(PASS, prefix + "color-mode", "RGBA")
    else:
        report.add(FAIL, prefix + "color-mode", f"{mode}, required RGBA (ASSET_SPEC 4)")

    return header


def check_pixels(path, report, prefix=""):
    """Color space and alpha: transparent background, clean edge, real coverage."""
    Image = load_pillow()
    names = ["color-space", "alpha/background", "alpha/edge", "alpha/coverage"]
    if Image is None:
        for name in names:
            report.add(SKIP, prefix + name, "Pillow not installed - run: pip install Pillow")
        return

    with Image.open(path) as img:
        if img.info.get("icc_profile"):
            report.add(WARN, prefix + "color-space",
                       "embedded ICC profile found - strip it, the pipeline assumes sRGB "
                       "(ASSET_SPEC 3)")
        else:
            report.add(PASS, prefix + "color-space", "no embedded ICC profile, assumed sRGB")

        if img.mode != "RGBA":
            for name in names[1:]:
                report.add(SKIP, prefix + name, "image is not RGBA")
            return

        alpha = img.getchannel("A")
        width, height = img.size
        corners = [
            alpha.getpixel((0, 0)),
            alpha.getpixel((width - 1, 0)),
            alpha.getpixel((0, height - 1)),
            alpha.getpixel((width - 1, height - 1)),
        ]
        if all(value == 0 for value in corners):
            report.add(PASS, prefix + "alpha/background", "all four corners fully transparent")
        else:
            report.add(FAIL, prefix + "alpha/background",
                       f"corner alpha {corners}, expected [0, 0, 0, 0] - background is not "
                       "transparent (ASSET_SPEC 4)")

        histogram = alpha.histogram()
        total = float(width * height)
        semi_fraction = (total - histogram[0] - histogram[255]) / total
        if semi_fraction <= MAX_SEMI_TRANSPARENT_FRACTION:
            report.add(PASS, prefix + "alpha/edge", f"{semi_fraction:.2%} semi-transparent")
        else:
            report.add(FAIL, prefix + "alpha/edge",
                       f"{semi_fraction:.2%} semi-transparent, max "
                       f"{MAX_SEMI_TRANSPARENT_FRACTION:.0%} - soft matte or halo from the "
                       "generation background (ASSET_SPEC 4)")

        opaque_fraction = histogram[255] / total
        if MIN_OPAQUE_FRACTION <= opaque_fraction <= MAX_OPAQUE_FRACTION:
            report.add(PASS, prefix + "alpha/coverage", f"{opaque_fraction:.1%} of frame opaque")
        else:
            report.add(FAIL, prefix + "alpha/coverage",
                       f"{opaque_fraction:.1%} of frame opaque, expected "
                       f"{MIN_OPAQUE_FRACTION:.0%}-{MAX_OPAQUE_FRACTION:.0%} - cutout is "
                       "empty or the background was not removed")


def silhouette_bbox(path):
    """Bounding box of the opaque silhouette, normalized. None without Pillow."""
    Image = load_pillow()
    if Image is None:
        return None
    with Image.open(path) as img:
        if img.mode != "RGBA":
            return None
        bbox = img.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
        if bbox is None:
            return None
        width, height = img.size
        left, top, right, bottom = bbox
        return {
            "left": left / width,
            "top": top / height,
            "right": right / width,
            "bottom": bottom / height,
        }


def changed_region(reference_path, asset_path, threshold=8):
    """Bounding box of pixels that differ from the reference, normalized.

    This is what makes "change only the mouth" checkable instead of a matter of
    opinion: whatever moved between the reference and a derived asset shows up
    here, and it either falls inside the permitted edit region or it does not.

    Returns (bbox or None, changed_fraction), or None without Pillow.
    threshold is per-channel and absorbs PNG re-encoding noise, not real edits.
    """
    Image = load_pillow()
    if Image is None:
        return None
    from PIL import ImageChops

    with Image.open(reference_path) as ref, Image.open(asset_path) as asset:
        ref = ref.convert("RGBA")
        asset = asset.convert("RGBA")
        if ref.size != asset.size:
            return None
        width, height = ref.size
        diff = ImageChops.difference(ref, asset)
        combined = diff.split()[0]
        for band in diff.split()[1:]:
            combined = ImageChops.lighter(combined, band)
        mask = combined.point(lambda value: 255 if value > threshold else 0)

    bbox = mask.getbbox()
    changed = mask.histogram()[255] / float(width * height)
    if bbox is None:
        return None, 0.0
    left, top, right, bottom = bbox
    return {
        "left": left / width,
        "top": top / height,
        "right": right / width,
        "bottom": bottom / height,
    }, changed
