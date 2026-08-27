#!/usr/bin/env python3
"""Build a contact sheet for side-by-side asset review (PHASE 3.4).

ASSET_SPEC.md section 10 requires an expression to be legible at 256px and distinct
from every other expression in the set, and MBP to be distinguishable from REST at
the same size. Neither is judgeable one image at a time, so QC needs a sheet.

Cells are rendered at 256px because that is the size at which subtle identity drift
stops being deniable. The reference is always the first cell, as the thing everything
else is compared against.

Usage:
    contact_sheet.py --set expression
    contact_sheet.py --all
    contact_sheet.py --set viseme --out assets/contact-sheets/narra-sheet-visemes-v1.png
    contact_sheet.py a.png b.png --label-from-filename

Exit code 0 = sheet written, 1 = nothing to render, 2 = usage error.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import canon                                     # noqa: E402
import imagecheck                                # noqa: E402

REPO = Path(os.environ.get("NARRA_REPO", Path(__file__).resolve().parents[2]))
SHEET_DIR = REPO / "assets" / "contact-sheets"

ASSET_DIRS = {
    "expression": REPO / "character" / "expressions",
    "viseme": REPO / "character" / "visemes",
    "pose": REPO / "character" / "poses",
}

CELL = 256          # ASSET_SPEC.md section 10 review size
LABEL_HEIGHT = 20
PADDING = 8
COLUMNS = 6
# Mid grey rather than white or black: a flat background hides alpha halos on one
# end of the value range or the other, and a halo is exactly what QC is looking for.
BACKGROUND = (128, 128, 128, 255)
LABEL_BG = (32, 32, 32, 255)
LABEL_FG = (240, 240, 240, 255)


def reference_cell():
    path = REPO / "character" / "reference" / f"{canon.CHARACTER}-reference-master-v1.png"
    return (path, "REFERENCE") if path.exists() else None


def set_cells(asset_type):
    """Canonical order, so the sheet reads the same way every time it is built."""
    directory = ASSET_DIRS[asset_type]
    cells = []
    for name in canon.CANONICAL[asset_type]:
        matches = sorted(directory.glob(
            canon.asset_filename(asset_type, name, version=0).replace("-v0.png", "-v*.png")))
        if matches:
            cells.append((matches[-1], name))
    return cells


def sheet_path(asset_type):
    """Where the PHASE 6 gate looks for a set's review sheet (ASSET_SPEC 5)."""
    return SHEET_DIR / f"{canon.CHARACTER}-sheet-{asset_type}s-v1.png"


def build(cells, out_path, columns=COLUMNS):
    Image = imagecheck.load_pillow()
    if Image is None:
        print("error: Pillow is required to build a contact sheet - pip install Pillow",
              file=sys.stderr)
        return 2
    from PIL import ImageDraw, ImageFont

    rows = (len(cells) + columns - 1) // columns
    cell_h = CELL + LABEL_HEIGHT
    width = columns * (CELL + PADDING) + PADDING
    height = rows * (cell_h + PADDING) + PADDING

    sheet = Image.new("RGBA", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default()
    except OSError:
        font = None

    for index, (path, label) in enumerate(cells):
        column, row = index % columns, index // columns
        x = PADDING + column * (CELL + PADDING)
        y = PADDING + row * (cell_h + PADDING)

        with Image.open(path) as img:
            thumb = img.convert("RGBA").resize((CELL, CELL), Image.LANCZOS)
        sheet.alpha_composite(thumb, (x, y))

        draw.rectangle([x, y + CELL, x + CELL, y + cell_h], fill=LABEL_BG)
        draw.text((x + 4, y + CELL + 5), label, fill=LABEL_FG, font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    print(f"Wrote {out_path} - {len(cells)} cell(s), {columns}x{rows} at {CELL}px")
    return 0


def build_all(columns=COLUMNS, no_reference=False):
    """PHASE 6.2: one review sheet per set, at the paths the gate checks.

    Every set gets a sheet even when it is incomplete - a sheet of nine expressions
    is how the tenth gets noticed. An empty set is the one case with nothing to show.
    """
    reference = None if no_reference else reference_cell()
    written, empty = [], []
    for asset_type in ("expression", "viseme", "pose"):
        assets = set_cells(asset_type)
        if not assets:
            empty.append(asset_type)
            continue
        code = build(([reference] if reference else []) + assets,
                     sheet_path(asset_type), columns)
        if code != 0:
            return code
        written.append(asset_type)

    for asset_type in empty:
        print(f"skipped {asset_type} - no assets in "
              f"{ASSET_DIRS[asset_type].relative_to(REPO)}", file=sys.stderr)
    if not written:
        print("error: no assets in any set - nothing to review", file=sys.stderr)
        return 1
    return 1 if empty else 0


def main():
    parser = argparse.ArgumentParser(
        description="Build a contact sheet for side-by-side asset review (PHASE 3.4).")
    parser.add_argument("assets", nargs="*", type=Path, help="explicit asset PNGs")
    parser.add_argument("--set", dest="asset_set",
                        help="build from a canonical set: expression, viseme, pose")
    parser.add_argument("--all", action="store_true",
                        help="build the review sheet for every set (PHASE 6.2)")
    parser.add_argument("--out", type=Path, help="output path")
    parser.add_argument("--columns", type=int, default=COLUMNS)
    parser.add_argument("--no-reference", action="store_true",
                        help="omit the reference cell")
    args = parser.parse_args()

    if args.asset_set and args.assets:
        parser.error("--set builds from a canonical set; do not also name assets")
    if args.all and (args.asset_set or args.assets or args.out):
        parser.error("--all builds every set to its default path; use --set for one sheet")
    if not args.all and not args.asset_set and not args.assets:
        parser.error("name some assets, or use --set, or --all")
    if args.columns < 1:
        parser.error("--columns must be at least 1")

    if args.all:
        return build_all(args.columns, args.no_reference)

    cells = []
    if not args.no_reference:
        reference = reference_cell()
        if reference:
            cells.append(reference)

    if args.asset_set:
        if args.asset_set not in ASSET_DIRS:
            print(f"error: unknown set {args.asset_set!r}", file=sys.stderr)
            return 2
        cells.extend(set_cells(args.asset_set))
        default_out = sheet_path(args.asset_set)
    else:
        missing = [path for path in args.assets if not path.exists()]
        if missing:
            print(f"error: not found: {', '.join(str(p) for p in missing)}", file=sys.stderr)
            return 2
        cells.extend((path, path.stem) for path in args.assets)
        default_out = SHEET_DIR / f"{canon.CHARACTER}-sheet-custom-v1.png"

    if not cells:
        print("error: nothing to render - no reference and no assets found", file=sys.stderr)
        return 1

    return build(cells, args.out or default_out, args.columns)


if __name__ == "__main__":
    sys.exit(main())
