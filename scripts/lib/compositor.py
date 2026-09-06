"""Layer compositing - expression plus blended viseme mouth (PHASE 8).

ADR-004 keeps expression and viseme on separate layers, and ASSET_SPEC section 7 says a
viseme differs from REST only inside the permitted `edit_region`. Those two facts are
what make compositing possible at all: the mouth region of a viseme can be lifted and
placed onto any expression, because everything outside that box is the same image.

So a frame is:

    expression asset
    + weighted blend of the frame's viseme mouth regions
    -> one 1024x1024 RGBA frame

The blend is a weighted average inside the edit region only. It is done on
non-premultiplied RGBA, which is exact here because the edit region sits inside the
face where alpha is fully opaque - `check_region_opaque` verifies that rather than
assuming it.

Requires a measured mouth anchor (PHASE 4.3). Without one there is no edit region and
no way to know where the mouth is; this refuses rather than guessing.

Not a package (DECISIONS.md ADR-007, ADR-011).
"""

import json
from pathlib import Path

import canon

EXPECTED_SIZE = (1024, 1024)


class CompositorError(Exception):
    """An asset, the anchor, or Pillow is missing, or an asset is the wrong shape."""


def load_pillow():
    try:
        from PIL import Image
    except ImportError as error:                       # pragma: no cover
        raise CompositorError(
            "Pillow is required to render frames - the frame plan itself needs no "
            "dependency, only rendering does") from error
    return Image


def load_anchor(repo):
    """The measured mouth anchor, or a refusal that says how to measure it."""
    path = Path(repo) / "character" / "bible" / "mouth-anchor.json"
    if not path.exists():
        raise CompositorError(f"mouth anchor not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("status") != "measured" or not data.get("edit_region"):
        raise CompositorError(
            "the mouth anchor is unmeasured, so there is no edit region and no way to "
            "know where the mouth is (PHASE 4.3). Measure it from the approved "
            "reference: python3 scripts/utilities/measure_anchor.py --box L T R B")
    return data


def edit_box(anchor, size=EXPECTED_SIZE):
    """The permitted edit region as an integer pixel box."""
    region = anchor["edit_region"]
    width, height = size
    box = (int(round(region["left"] * width)), int(round(region["top"] * height)),
           int(round(region["right"] * width)), int(round(region["bottom"] * height)))
    if box[0] >= box[2] or box[1] >= box[3]:
        raise CompositorError(f"edit_region is empty or inverted: {region}")
    return box


def asset_path(repo, asset_type, name, version=1):
    folder = {"expression": "expressions", "viseme": "visemes",
              "pose": "poses"}[asset_type]
    return (Path(repo) / "character" / folder
            / canon.asset_filename(asset_type, name, version))


def open_asset(path):
    Image = load_pillow()
    if not Path(path).exists():
        raise CompositorError(f"asset not found: {path}")
    image = Image.open(path).convert("RGBA")
    if image.size != EXPECTED_SIZE:
        raise CompositorError(
            f"{path} is {image.size[0]}x{image.size[1]}, expected "
            f"{EXPECTED_SIZE[0]}x{EXPECTED_SIZE[1]} (ASSET_SPEC 1)")
    return image


def check_region_opaque(image, box, threshold=250):
    """Is the edit region fully opaque? Decides whether a plain blend is exact."""
    alpha = image.crop(box).getchannel("A")
    return alpha.getextrema()[0] >= threshold


def blend_layers(images, weights):
    """Weighted average of images. Weights are normalised; order does not matter.

    Successive pairwise blending, which is exactly a weighted mean when each step is
    weighted by that layer's share of the running total.
    """
    Image = load_pillow()
    if not images:
        raise CompositorError("nothing to blend")
    if len(images) == 1:
        return images[0].copy()

    total = float(sum(weights))
    if total <= 0:
        raise CompositorError("blend weights sum to zero")

    accumulated = images[0].copy()
    accumulated_weight = weights[0] / total
    for image, weight in zip(images[1:], weights[1:]):
        share = weight / total
        if accumulated_weight + share <= 0:
            continue
        accumulated = Image.blend(accumulated, image,
                                  share / (accumulated_weight + share))
        accumulated_weight += share
    return accumulated


class FrameRenderer:
    """Renders frames, caching the assets so each file is decoded once."""

    def __init__(self, repo, anchor=None, version=1):
        self.repo = Path(repo)
        self.anchor = anchor or load_anchor(repo)
        self.box = edit_box(self.anchor)
        self.version = version
        self._expressions = {}
        self._mouths = {}
        self.warnings = []

    def expression(self, name):
        if name not in self._expressions:
            image = open_asset(asset_path(self.repo, "expression", name, self.version))
            if not check_region_opaque(image, self.box):
                self.warnings.append(
                    f"expression {name}: the edit region is not fully opaque, so a "
                    "plain RGBA blend is approximate there")
            self._expressions[name] = image
        return self._expressions[name]

    def mouth(self, viseme):
        """The viseme's edit region only - everything outside it is the same image."""
        if viseme not in self._mouths:
            image = open_asset(asset_path(self.repo, "viseme", viseme, self.version))
            self._mouths[viseme] = image.crop(self.box)
        return self._mouths[viseme]

    def render(self, expression, layers):
        """One composited frame."""
        base = self.expression(expression).copy()
        if not layers:
            return base
        mouths = [self.mouth(layer["viseme"]) for layer in layers]
        weights = [layer["weight"] for layer in layers]
        base.paste(blend_layers(mouths, weights), self.box)
        return base

    def required_assets(self, plan):
        """Every asset the plan needs, and whether it is on disk."""
        expressions = {segment["expression"] for segment in plan["tracks"]["expression"]}
        visemes = {layer["viseme"] for frame in plan["tracks"]["mouth"]
                   for layer in frame["layers"]}
        missing = []
        for name in sorted(expressions):
            path = asset_path(self.repo, "expression", name, self.version)
            if not path.exists():
                missing.append(str(path))
        for name in sorted(visemes):
            path = asset_path(self.repo, "viseme", name, self.version)
            if not path.exists():
                missing.append(str(path))
        return sorted(expressions), sorted(visemes), missing


def expression_at(segments, time):
    """Which expression is underneath at this instant."""
    for segment in segments:
        if segment["start"] - 1e-9 <= time < segment["end"] + 1e-9:
            return segment["expression"]
    return segments[-1]["expression"] if segments else None
