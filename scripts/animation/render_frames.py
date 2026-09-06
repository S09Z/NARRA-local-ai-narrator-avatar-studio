#!/usr/bin/env python3
"""Render a frame plan to PNG frames (PHASE 8).

    animation.json + character assets -> assets/frames/<name>/frame-000000.png

This is the step that needs the image library to exist. Everything before it is data.
Run --check first: it reports exactly which assets the plan needs and which are missing,
without decoding anything.

Requires a measured mouth anchor (PHASE 4.3). Without one there is no edit region, so
there is no way to know where to put the mouth, and this refuses rather than guessing.

Usage:
    render_frames.py animation.json --check
    render_frames.py animation.json --out-dir assets/frames/greeting
    render_frames.py animation.json --range 0:50
    render_frames.py animation.json --contact-sheet sheet.png

Exit code 0 = rendered, 1 = cannot render, 2 = usage error.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import compositor as compositor_lib                   # noqa: E402

REPO = Path(os.environ.get("NARRA_REPO", Path(__file__).resolve().parents[2]))
FRAME_DIR = REPO / "assets" / "frames"


def parse_range(text, count):
    if not text:
        return 0, count
    start, _, end = text.partition(":")
    return int(start or 0), int(end or count)


def check(plan, renderer):
    """What the plan needs, and what is missing. Decodes nothing."""
    expressions, visemes, missing = renderer.required_assets(plan)
    print(f"frames        {plan['frame_count']} at {plan['fps']}fps")
    print(f"expressions   {', '.join(expressions)}")
    print(f"visemes       {', '.join(visemes)}")
    if missing:
        print(f"\nmissing {len(missing)} asset(s):")
        for path in missing:
            print(f"  {path}")
        return 1
    print("\nall required assets are present")
    return 0


def contact_sheet(images, path, columns=8, thumb=128):
    """A quick strip of the rendered frames, for looking at the motion at a glance."""
    Image = compositor_lib.load_pillow()
    if not images:
        return None
    rows = (len(images) + columns - 1) // columns
    sheet = Image.new("RGBA", (columns * thumb, rows * thumb), (0, 0, 0, 0))
    for index, image in enumerate(images):
        scaled = image.resize((thumb, thumb), Image.LANCZOS)
        sheet.paste(scaled, ((index % columns) * thumb, (index // columns) * thumb))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render a frame plan (PHASE 8).")
    parser.add_argument("animation", help="animation JSON from build_animation.py")
    parser.add_argument("--out-dir", help="where to write frames")
    parser.add_argument("--name", help="subdirectory under assets/frames")
    parser.add_argument("--range", dest="frame_range", help="START:END frame range")
    parser.add_argument("--check", action="store_true",
                        help="report required assets and exit without rendering")
    parser.add_argument("--contact-sheet", help="also write a strip of the frames")
    parser.add_argument("--version", type=int, default=1, help="asset version")
    args = parser.parse_args(argv)

    try:
        plan = json.loads(Path(args.animation).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    try:
        renderer = compositor_lib.FrameRenderer(REPO, version=args.version)
    except compositor_lib.CompositorError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if args.check:
        return check(plan, renderer)

    _, _, missing = renderer.required_assets(plan)
    if missing:
        print(f"error: {len(missing)} required asset(s) missing - run --check to list "
              "them", file=sys.stderr)
        return 1

    frames = plan["tracks"]["mouth"]
    segments = plan["tracks"]["expression"]
    start, end = parse_range(args.frame_range, len(frames))

    name = args.name or Path(args.animation).stem
    out_dir = Path(args.out_dir) if args.out_dir else FRAME_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)

    rendered = []
    try:
        for frame in frames[start:end]:
            expression = compositor_lib.expression_at(segments, frame["time"])
            image = renderer.render(expression, frame["layers"])
            path = out_dir / f"frame-{frame['frame']:06d}.png"
            image.save(path)
            rendered.append(image)
    except compositor_lib.CompositorError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"{out_dir}")
    print(f"  rendered      {len(rendered)} frame(s) [{start}:{end}]")
    for warning in renderer.warnings:
        print(f"  warning: {warning}")
    if args.contact_sheet:
        sheet = contact_sheet(rendered, args.contact_sheet)
        print(f"  contact sheet {sheet}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
