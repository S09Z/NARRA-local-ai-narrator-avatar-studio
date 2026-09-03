#!/usr/bin/env python3
"""Run the PHASE 6 gate and write the production lock (PLAN.md section 6).

PHASE 6 is the hard gate before any video work. The question it answers is narrow:
is the image library complete, validated, signed for, and reproducible from its own
metadata? That is currently spread across three set checks, thirty-eight validation
records, and a person's memory, which is exactly the kind of thing that gets
declared "done" a week before someone discovers the viseme set was missing SH.

What this script will not do is decide the visual half. `validate_asset.py --approve`
records a person's sign-off against ASSET_SPEC 10; the gate only reads those records.
An asset nobody looked at cannot be locked no matter how clean its pixels are.

The lock is `metadata/production-lock.json`: every locked asset with its sha256,
seed, model, workflow, and prompt version. `--verify` re-checks the files against it,
which is how a silent edit to a locked asset gets caught before it reaches PHASE 8.
`docs/production-baseline.md` (PLAN 6.5) is generated from the lock rather than
maintained by hand, because a hand-maintained baseline is stale the first time
anyone regenerates an asset and forgets.

Usage:
    lock_library.py                       run the gate, report, write nothing
    lock_library.py --lock --by "name"    gate must pass, then write the lock
    lock_library.py --verify              re-check the written lock against the files
    lock_library.py --baseline            regenerate docs/production-baseline.md

Exit code 0 = passed, 1 = failed, 2 = usage error.
"""

import argparse
import contextlib
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import canon                                                  # noqa: E402
import imagecheck                                             # noqa: E402
import validate_asset as assetcheck                           # noqa: E402
import validate_compositions as compcheck                     # noqa: E402
import validate_reference as refcheck                         # noqa: E402
from imagecheck import FAIL, PASS, SKIP, WARN, Report, sha256  # noqa: E402

REPO = Path(os.environ.get("NARRA_REPO", Path(__file__).resolve().parents[2]))
LOCK_FILE = REPO / "metadata" / "production-lock.json"
BASELINE_DOC = REPO / "docs" / "production-baseline.md"
GENERATIONS = REPO / "metadata" / "generations"
VALIDATION_DIR = REPO / "metadata" / "validation"
SHEET_DIR = REPO / "assets" / "contact-sheets"

# ASSET_SPEC.md section 1 / DECISIONS.md ADR-017: an upscale is a derivative of a
# locked master, kept outside character/ so it can never be mistaken for a library
# asset or used as the input to a further edit.
UPSCALE_DIR = REPO / "assets" / "approved" / "upscaled"
UPSCALE_SUFFIX = "-up2048"
UPSCALE_SIZE = (2048, 2048)

SET_ORDER = ["expression", "viseme", "pose"]
LOCKED_RESOLUTION = list(imagecheck.REQUIRED_SIZE)

# ASSET_SPEC 9 head-drift tolerance, applied within a camera class rather than
# against the close-up reference (character/bible/visual-spec.md section 2).
CROWN_SPREAD_MAX = assetcheck.HEAD_DRIFT_MAX


def rel(path):
    path = Path(path)
    return str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path)


def failures(report):
    """The FAIL rows of a sub-report, flattened into one line each."""
    return [f"{name}: {detail}" for level, name, detail in report.rows if level == FAIL]


def library_assets(asset_type):
    """Latest version of each canonical asset, plus anything that does not belong."""
    directory = assetcheck.ASSET_DIRS[asset_type]
    found, strays = {}, []
    if not directory.exists():
        return found, strays
    for path in sorted(directory.glob("*.png")):
        fields = canon.parse_filename(path.stem)
        if (fields is None or fields["asset_type"] != asset_type
                or canon.index_of(asset_type, fields["name"]) is None):
            strays.append(path)
            continue
        name = canon.canonical_name(asset_type, fields["name"])
        current = found.get(name)
        if current is None or int(fields["version"]) >= int(
                canon.parse_filename(current.stem)["version"]):
            found[name] = path
    return found, strays


def load_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


# --- gate checks -----------------------------------------------------------


def check_counts(report):
    """PLAN 6.1. Guards the numbers the gate is made of.

    The completeness requirement is only meaningful if the canonical set still holds
    the count the plan asked for - otherwise dropping a viseme would silently move
    the finish line rather than fail the gate.
    """
    for asset_type in SET_ORDER:
        required = canon.REQUIRED_COUNTS[asset_type]
        actual = len(canon.CANONICAL[asset_type])
        if actual != required:
            report.add(FAIL, f"canon/{asset_type}",
                       f"the canonical set holds {actual} names, PLAN 6.1 requires "
                       f"{required}")
        else:
            report.add(PASS, f"canon/{asset_type}", f"{required} names")


def check_reference(report):
    """The whole library is derived from one image; it has to still be that image."""
    sub = Report()
    refcheck.check_imported(sub)
    if refcheck.MASTER.exists() and imagecheck.check_header(refcheck.MASTER, sub):
        imagecheck.check_pixels(refcheck.MASTER, sub)

    bad = failures(sub)
    if bad:
        report.add(FAIL, "reference/master", "; ".join(bad))
        return None
    digest = sha256(refcheck.MASTER)
    report.add(PASS, "reference/master", f"{rel(refcheck.MASTER)} sha256 {digest[:12]}")
    return {"file": rel(refcheck.MASTER), "sha256": digest}


def check_anchor(report):
    """ASSET_SPEC 9. Without a measured anchor the viseme layer has no contract."""
    if not assetcheck.ANCHOR_FILE.exists():
        report.add(FAIL, "anchor/measured",
                   f"{rel(assetcheck.ANCHOR_FILE)} missing")
        return None
    doc = load_json(assetcheck.ANCHOR_FILE)
    if doc is None:
        report.add(FAIL, "anchor/measured", "mouth-anchor.json is not valid JSON")
        return None

    anchor = doc.get("anchor") or {}
    if doc.get("status") != "measured" or anchor.get("anchor_x") is None:
        report.add(FAIL, "anchor/measured",
                   "the mouth anchor is unmeasured - measure it from the approved "
                   "reference with scripts/utilities/measure_anchor.py (PHASE 4.3)")
        return None
    report.add(PASS, "anchor/measured",
               f"x={anchor['anchor_x']:.3f} y={anchor['anchor_y']:.3f}")

    if not doc.get("edit_region"):
        report.add(FAIL, "anchor/edit-region",
                   "no edit region recorded, so viseme containment was never actually "
                   "measured (DECISIONS.md ADR-013)")
    else:
        report.add(PASS, "anchor/edit-region", "recorded")
    return doc


def load_review(path):
    """The QC record written by validate_asset.py --record / --approve."""
    return load_json(VALIDATION_DIR / f"{path.stem}.json")


def check_asset(asset_type, name, path, report):
    """Every machine-checkable requirement for one asset, condensed to one row.

    The per-check detail belongs to validate_asset.py; repeating thirty-eight
    full reports here would bury the one line that matters.
    """
    label = f"{asset_type}/{name.lower()}"
    sub = Report()
    fields = assetcheck.check_naming(path, sub)
    if imagecheck.check_header(path, sub):
        imagecheck.check_pixels(path, sub)
    data = assetcheck.check_sidecar(path, fields, sub)
    assetcheck.check_drift(path, data, sub)
    assetcheck.check_containment(path, fields, sub)
    bad = failures(sub)

    review = load_review(path)
    if review is None:
        bad.append("review: no QC record in metadata/validation/ - validate it and sign "
                   "off with validate_asset.py --approve")
    elif review.get("overall") != "approved":
        bad.append(f"review: recorded as {review.get('overall')!r}, not approved - the "
                   "identity checks in ASSET_SPEC 10 are visual and need a reviewer")

    if bad:
        report.add(FAIL, label, "; ".join(bad))
        return None

    mirror = GENERATIONS / f"{path.stem}.json"
    if not mirror.exists():
        report.add(WARN, label,
                   f"{path.name} ready; metadata/generations/{mirror.name} will be "
                   "written by --lock (ASSET_SPEC 11)")
    elif mirror.read_text() != path.with_suffix(".json").read_text():
        report.add(FAIL, label,
                   f"mirror: metadata/generations/{mirror.name} differs from the sidecar "
                   "- two records of the same generation disagree")
        return None
    else:
        report.add(PASS, label, f"{path.name} sha256 {sha256(path)[:12]}")

    return {"type": asset_type, "name": name, "path": path, "data": data,
            "review": review}


def check_set(asset_type, report):
    """PLAN 6.1 completeness, then every asset in the set."""
    found, strays = library_assets(asset_type)
    expected = canon.CANONICAL[asset_type]

    missing = [name for name in expected if name not in found]
    if missing:
        report.add(FAIL, f"{asset_type}/complete",
                   f"{len(found)}/{len(expected)} present, missing: "
                   f"{', '.join(missing)} (PLAN 6.1)")
    else:
        report.add(PASS, f"{asset_type}/complete", f"{len(expected)}/{len(expected)} present")

    for path in strays:
        report.add(FAIL, f"{asset_type}/stray",
                   f"{path.name} is not in the canonical {asset_type} set - the locked "
                   "library holds exactly the canonical set and nothing else")

    entries = []
    for name in expected:
        path = found.get(name)
        if path is None:
            continue
        entry = check_asset(asset_type, name, path, report)
        if entry is not None:
            entries.append(entry)
    return entries


def check_sheets(state, report):
    """PLAN 6.2. Distinctness is judged side by side, so the sheets have to exist."""
    for asset_type in SET_ORDER:
        sheet = SHEET_DIR / f"{canon.CHARACTER}-sheet-{asset_type}s-v1.png"
        label = f"sheet/{asset_type}"
        if not sheet.exists():
            report.add(FAIL, label,
                       f"{rel(sheet)} missing - build the review sheets with "
                       "scripts/utilities/contact_sheet.py --all (PLAN 6.2)")
            continue
        newer = [entry["name"] for entry in state["sets"].get(asset_type, [])
                 if entry["path"].stat().st_mtime > sheet.stat().st_mtime]
        if newer:
            report.add(WARN, label,
                       f"{rel(sheet)} is older than {', '.join(newer)} - rebuild it or "
                       "the review was of a different image")
        else:
            report.add(PASS, label, rel(sheet))


def check_camera_classes(state, report):
    """ASSET_SPEC 8: head position is consistent *within* a camera class.

    Poses are framed differently from the close-up reference on purpose, so per-asset
    drift against the reference is not the measurement for them - which leaves the
    consistency that actually matters unchecked until here. Two poses in the same
    class have to intercut, and if their crowns sit at different heights they will not.

    Only the crown is measured. Head *height* needs to separate head from body, which
    an alpha channel cannot do, so it stays in the human checklist (ASSET_SPEC 10).
    """
    groups = {}
    for entry in state["sets"].get("pose", []):
        camera_class = (entry["data"] or {}).get("camera_class")
        box = imagecheck.silhouette_bbox(entry["path"])
        if not camera_class:
            continue
        if box is None:
            report.add(SKIP, f"framing/{camera_class}",
                       "Pillow not installed, or the cutout is empty")
            return
        groups.setdefault(camera_class, []).append((entry["name"], box["top"]))

    if not groups:
        report.add(SKIP, "framing/camera-classes", "no pose assets to compare")
        return

    for camera_class in sorted(groups):
        members = groups[camera_class]
        crowns = [top for _, top in members]
        spread = max(crowns) - min(crowns)
        names = ", ".join(name for name, _ in members)
        if len(members) == 1:
            report.add(PASS, f"framing/{camera_class}", f"{names} (only member)")
        elif spread <= CROWN_SPREAD_MAX:
            report.add(PASS, f"framing/{camera_class}",
                       f"{len(members)} poses, crown spread {spread:.3%} of height "
                       f"({spread * 1024:.1f}px at 1024)")
        else:
            report.add(FAIL, f"framing/{camera_class}",
                       f"crown spread {spread:.3%} of height across {names}, max "
                       f"{CROWN_SPREAD_MAX:.0%} - poses in one class must intercut "
                       "(ASSET_SPEC 8, visual-spec.md 2)")


def check_compositions(report):
    """PHASE 5.3 states name assets; at lock time they must still resolve."""
    path = compcheck.DEFAULT
    if not path.exists():
        report.add(FAIL, "compositions", f"{rel(path)} missing (PLAN 5.3)")
        return
    with contextlib.redirect_stdout(io.StringIO()):
        code = compcheck.validate(path)
    if code == 0:
        report.add(PASS, "compositions", rel(path))
    else:
        report.add(FAIL, "compositions",
                   f"{rel(path)} does not validate - run "
                   "scripts/validation/validate_compositions.py for the detail")


def check_upscales(state, report):
    """ASSET_SPEC 1 / ADR-017. Upscaling is optional; doing it sloppily is not.

    An upscale that cannot name the exact master it came from is not a derivative,
    it is a second, unreproducible asset with the same face.
    """
    masters = {entry["path"].stem: entry
               for entries in state["sets"].values() for entry in entries}
    files = sorted(UPSCALE_DIR.glob("*.png")) if UPSCALE_DIR.exists() else []
    if not files:
        report.add(SKIP, "upscale/derivatives",
                   "none present - upscaling is optional (ASSET_SPEC 1)")
        return []

    records = []
    for path in files:
        label = f"upscale/{path.stem}"
        if not path.stem.endswith(UPSCALE_SUFFIX):
            report.add(FAIL, label,
                       f"expected a name ending in {UPSCALE_SUFFIX} (ADR-017)")
            continue
        master_stem = path.stem[: -len(UPSCALE_SUFFIX)]
        master = masters.get(master_stem)
        if master is None:
            report.add(FAIL, label,
                       f"{master_stem} is not an approved master in the locked library "
                       "- only locked assets may be upscaled (ASSET_SPEC 1)")
            continue

        header = imagecheck.read_png_header(path)
        if header is None or header[:2] != UPSCALE_SIZE or header[3] != "RGBA":
            report.add(FAIL, label,
                       f"expected {UPSCALE_SIZE[0]}x{UPSCALE_SIZE[1]} RGBA PNG, "
                       f"found {header[0]}x{header[1]} {header[3]}" if header
                       else "not a PNG file")
            continue

        sidecar = load_json(path.with_suffix(".json"))
        if sidecar is None:
            report.add(FAIL, label, f"{path.stem}.json missing (ASSET_SPEC 11)")
            continue
        recorded = sidecar.get("derived_from_sha256")
        if sidecar.get("derived_from") != rel(master["path"]):
            report.add(FAIL, label,
                       f"derived_from is {sidecar.get('derived_from')!r}, expected "
                       f"{rel(master['path'])!r}")
        elif recorded != sha256(master["path"]):
            report.add(FAIL, label,
                       "derived_from_sha256 does not match the master - this was "
                       "upscaled from a version of the asset that no longer exists")
        else:
            report.add(PASS, label, f"from {master['path'].name}")
            records.append({
                "file": rel(path),
                "sha256": sha256(path),
                "derived_from": rel(master["path"]),
                "derived_from_sha256": recorded,
                "resolution": list(UPSCALE_SIZE),
                "upscaler": sidecar.get("upscaler"),
            })
    return records


def run_gate(report):
    """Every PHASE 6 requirement that a machine can settle."""
    check_counts(report)
    state = {"reference": check_reference(report), "anchor": check_anchor(report),
             "sets": {}}
    for asset_type in SET_ORDER:
        state["sets"][asset_type] = check_set(asset_type, report)
    check_camera_classes(state, report)
    check_sheets(state, report)
    check_compositions(report)
    state["upscales"] = check_upscales(state, report)
    return state


# --- the lock --------------------------------------------------------------


def unique(values):
    """Distinct dicts, order preserved. Dicts are not hashable; their JSON is."""
    seen, out = set(), []
    for value in values:
        if value in (None, {}, []):
            continue
        key = json.dumps(value, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(value)
    return out


def all_entries(state):
    return [entry for asset_type in SET_ORDER for entry in state["sets"][asset_type]]


def asset_record(entry):
    data = entry["data"] or {}
    review = entry["review"] or {}
    record = {
        "name": entry["name"],
        "file": rel(entry["path"]),
        "sha256": sha256(entry["path"]),
        "metadata": rel(entry["path"].with_suffix(".json")),
        "version": data.get("version"),
        "seed": assetcheck.dig(data, "generation.seed"),
        "model": data.get("model"),
        "workflow": data.get("workflow"),
        "prompt_version": assetcheck.dig(data, "prompt.asset_prompt_version"),
        "master_prompt_version": assetcheck.dig(data, "prompt.master_version"),
        "generation": data.get("generation"),
        "mouth_anchor": data.get("mouth_anchor"),
        "generated_at": data.get("generated_at"),
        "reviewed_by": assetcheck.dig(review, "human_review.reviewer"),
        "reviewed_at": assetcheck.dig(review, "human_review.reviewed_at"),
    }
    if entry["type"] == "pose":
        record["camera_class"] = data.get("camera_class")
    return record


def build_lock(state, by):
    entries = all_entries(state)
    previous = load_json(LOCK_FILE) or {}
    anchor_doc = state["anchor"] or {}
    return {
        "$comment": ("PHASE 6 production lock (PLAN.md 6.4). Written by "
                     "scripts/validation/lock_library.py --lock; re-check the files "
                     "against it with --verify. Do not edit by hand."),
        "character": canon.CHARACTER,
        "lock_version": int(previous.get("lock_version", 0)) + 1,
        "locked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "locked_by": by,
        "gate": "PHASE 6 - Asset Validation & Production Lock",
        "resolution": LOCKED_RESOLUTION,
        "reference": state["reference"],
        "mouth_anchor": anchor_doc.get("anchor"),
        "edit_region": anchor_doc.get("edit_region"),
        "models": unique(entry["data"].get("model") for entry in entries),
        "workflows": unique(entry["data"].get("workflow") for entry in entries),
        "environments": unique(entry["data"].get("environment") for entry in entries),
        "prompt_versions": {
            "master": unique(assetcheck.dig(entry["data"], "prompt.master_version")
                             for entry in entries),
            **{asset_type: [assetcheck.dig(entry["data"], "prompt.asset_prompt_version")
                            for entry in state["sets"][asset_type]]
               for asset_type in SET_ORDER},
        },
        "sets": {
            asset_type: {
                "required": canon.REQUIRED_COUNTS[asset_type],
                "locked": len(state["sets"][asset_type]),
                "seed_base": canon.SEED_BASE[asset_type],
                "assets": [asset_record(entry) for entry in state["sets"][asset_type]],
            }
            for asset_type in SET_ORDER
        },
        "upscales": state["upscales"],
    }


def write_lock(state, by):
    """PLAN 6.4. Writing the lock is also what mirrors the metadata."""
    lock = build_lock(state, by)
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(json.dumps(lock, indent=2) + "\n")

    GENERATIONS.mkdir(parents=True, exist_ok=True)
    mirrored = 0
    for entry in all_entries(state):
        sidecar = entry["path"].with_suffix(".json")
        mirror = GENERATIONS / sidecar.name
        text = sidecar.read_text()
        if not mirror.exists() or mirror.read_text() != text:
            mirror.write_text(text)
            mirrored += 1

    write_baseline(lock)
    return lock, mirrored


def verify(report):
    """Does the library on disk still match what was locked?"""
    lock = load_json(LOCK_FILE)
    if lock is None:
        report.add(FAIL, "lock/file",
                   f"{rel(LOCK_FILE)} missing or invalid - nothing has been locked yet")
        return None
    report.add(PASS, "lock/file",
               f"v{lock.get('lock_version')} locked {lock.get('locked_at')} by "
               f"{lock.get('locked_by') or 'unrecorded'}")

    reference = lock.get("reference") or {}
    master = REPO / reference.get("file", "")
    if not master.exists():
        report.add(FAIL, "lock/reference", f"{reference.get('file')} is gone")
    elif sha256(master) != reference.get("sha256"):
        report.add(FAIL, "lock/reference",
                   "the reference changed since the lock - every asset below was "
                   "derived from a different image")
    else:
        report.add(PASS, "lock/reference", reference.get("file"))

    for asset_type in SET_ORDER:
        block = (lock.get("sets") or {}).get(asset_type) or {}
        assets = block.get("assets") or []
        required = canon.REQUIRED_COUNTS[asset_type]
        if len(assets) != required:
            report.add(FAIL, f"lock/{asset_type}",
                       f"{len(assets)} locked, {required} required (PLAN 6.1)")
        else:
            report.add(PASS, f"lock/{asset_type}", f"{required} assets")

        for record in assets:
            label = f"{asset_type}/{str(record.get('name')).lower()}"
            path = REPO / record.get("file", "")
            if not path.exists():
                report.add(FAIL, label, f"{record.get('file')} is gone")
                continue
            if sha256(path) != record.get("sha256"):
                report.add(FAIL, label,
                           "sha256 differs from the lock - the asset was edited or "
                           "regenerated without being re-locked")
                continue
            mirror = GENERATIONS / (path.stem + ".json")
            sidecar = path.with_suffix(".json")
            if not sidecar.exists():
                report.add(FAIL, label, "sidecar metadata is gone (ASSET_SPEC 11)")
            elif not mirror.exists() or mirror.read_text() != sidecar.read_text():
                report.add(FAIL, label,
                           "metadata/generations mirror is missing or out of date")
            else:
                report.add(PASS, label, path.name)

    for record in lock.get("upscales") or []:
        path = REPO / record.get("file", "")
        label = f"upscale/{path.stem}"
        if not path.exists():
            report.add(FAIL, label, f"{record.get('file')} is gone")
        elif sha256(path) != record.get("sha256"):
            report.add(FAIL, label, "sha256 differs from the lock")
        else:
            report.add(PASS, label, path.name)

    return lock


# --- docs/production-baseline.md (PLAN 6.5) --------------------------------


def table(rows, headers):
    widths = [max(len(str(row[i])) for row in [headers] + rows) for i in range(len(headers))]
    lines = ["| " + " | ".join(str(h).ljust(w) for h, w in zip(headers, widths)) + " |",
             "|" + "|".join("-" * (w + 2) for w in widths) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(c).ljust(w) for c, w in zip(row, widths)) + " |")
    return lines


def describe(value):
    if isinstance(value, dict):
        return ", ".join(f"{key}={value[key]}" for key in sorted(value) if value[key] not in (None, "", [], {}))
    if isinstance(value, list):
        return ", ".join(describe(item) for item in value) or "-"
    return "-" if value in (None, "") else str(value)


def baseline_lines(lock):
    """The generated PLAN 6.5 record. Generated, so it cannot go stale by hand."""
    lines = [
        "# PRODUCTION BASELINE",
        "",
        "PHASE 6.5 — the exact configuration the locked image library was produced with.",
        "",
        "**Generated file.** Written by `scripts/validation/lock_library.py`; every value",
        "below is read from the asset metadata, not typed in. Do not edit it by hand — the",
        "next lock overwrites it. To change a value here, regenerate the asset and re-lock.",
        "",
    ]

    if lock is None:
        lines += [
            "## Status",
            "",
            "**NOT LOCKED.** No `metadata/production-lock.json` has been written, so there",
            "is no baseline to record. PHASE 7 (Thai audio / phoneme) and everything after it",
            "remain blocked (PLAN.md — IMAGE PIPELINE GATE).",
            "",
            "To reach the lock:",
            "",
            "```",
            "python3 scripts/validation/lock_library.py            # what is still missing",
            "python3 scripts/utilities/contact_sheet.py --all      # PLAN 6.2 review sheets",
            "python3 scripts/validation/validate_asset.py <asset> --approve \"name\"",
            "python3 scripts/validation/lock_library.py --lock --by \"name\"",
            "```",
            "",
            "The gate requires, in order: an imported reference, a measured mouth anchor,",
            f"{canon.REQUIRED_COUNTS['expression']} expressions, "
            f"{canon.REQUIRED_COUNTS['viseme']} visemes, "
            f"{canon.REQUIRED_COUNTS['pose']} poses, a contact sheet per set, valid narrator",
            "compositions, and a recorded human sign-off for every asset.",
            "",
        ]
        return lines

    total = sum(len(lock["sets"][t]["assets"]) for t in SET_ORDER)
    lines += [
        "## Status",
        "",
        f"**LOCKED** — lock version {lock['lock_version']}, {lock['locked_at']}, "
        f"by {lock.get('locked_by') or 'unrecorded'}.",
        "",
        f"{total} assets locked at {lock['resolution'][0]}x{lock['resolution'][1]}.",
        "",
        "Verify the library still matches this baseline:",
        "",
        "```",
        "python3 scripts/validation/lock_library.py --verify",
        "```",
        "",
        "## Reference",
        "",
    ]
    reference = lock.get("reference") or {}
    lines += table([[reference.get("file", "-"), reference.get("sha256", "-")]],
                   ["file", "sha256"])
    anchor = lock.get("mouth_anchor") or {}
    if anchor:
        lines += ["", "Mouth anchor (ASSET_SPEC 9): " + describe(anchor)]
    if lock.get("edit_region"):
        lines += ["", "Permitted viseme edit region: " + describe(lock["edit_region"])]

    lines += ["", "## Models", ""]
    lines += table([[describe(model)] for model in lock.get("models") or [{}]] or [["-"]],
                   ["model"])

    lines += ["", "## Environment", ""]
    lines += table([[describe(env)] for env in lock.get("environments") or []] or [["-"]],
                   ["comfyui version / custom nodes"])

    lines += ["", "## Workflows", ""]
    lines += table([[describe(flow)] for flow in lock.get("workflows") or []] or [["-"]],
                   ["workflow"])

    prompts = lock.get("prompt_versions") or {}
    lines += ["", "## Prompt versions", "",
              "Master: " + describe(prompts.get("master")), ""]
    lines += table([[asset_type, canon.SEED_BASE[asset_type],
                     f"{canon.SEED_BASE[asset_type]}-"
                     f"{canon.SEED_BASE[asset_type] + canon.SEED_SPAN - 1}"]
                    for asset_type in SET_ORDER],
                   ["set", "seed base", "seed range"])

    for asset_type in SET_ORDER:
        block = lock["sets"][asset_type]
        lines += ["", f"## {asset_type.capitalize()} set "
                      f"({block['locked']}/{block['required']})", ""]
        headers = ["asset", "seed", "prompt", "settings", "sha256", "reviewer"]
        rows = []
        for record in block["assets"]:
            settings = {key: value for key, value in (record.get("generation") or {}).items()
                        if key not in ("seed", "resolution")}
            rows.append([
                record.get("name"),
                record.get("seed"),
                record.get("prompt_version"),
                describe(settings),
                (record.get("sha256") or "")[:12],
                record.get("reviewed_by") or "-",
            ])
        lines += table(rows, headers)

    if lock.get("upscales"):
        lines += ["", "## Upscale derivatives", ""]
        lines += table([[record["file"], record["derived_from"],
                         describe(record.get("upscaler"))]
                        for record in lock["upscales"]],
                       ["file", "derived from", "upscaler"])

    lines += ["", "## Gate", "",
              "PHASE 6 passed. PHASE 7 (Thai audio / phoneme pipeline) is unblocked.",
              "Regenerating any asset above invalidates this baseline: re-run the gate and",
              "re-lock.", ""]
    return lines


def write_baseline(lock):
    BASELINE_DOC.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_DOC.write_text("\n".join(baseline_lines(lock)).rstrip() + "\n")
    return BASELINE_DOC


# --- entry point -----------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Run the PHASE 6 gate and write the production lock (PLAN.md 6).")
    parser.add_argument("--lock", action="store_true",
                        help="write metadata/production-lock.json if the gate passes")
    parser.add_argument("--by", metavar="NAME",
                        help="who is locking the library; required with --lock")
    parser.add_argument("--verify", action="store_true",
                        help="re-check the written lock against the files")
    parser.add_argument("--baseline", action="store_true",
                        help="regenerate docs/production-baseline.md from the lock")
    args = parser.parse_args()

    if sum([args.lock, args.verify, args.baseline]) > 1:
        parser.error("--lock, --verify, and --baseline are separate operations")
    if args.lock and not args.by:
        parser.error("--lock needs --by \"name\" - a lock nobody signed is not a lock")

    if args.baseline:
        target = write_baseline(load_json(LOCK_FILE))
        print(f"Wrote {rel(target)}")
        return 0

    report = Report()

    if args.verify:
        print(f"Verifying {rel(LOCK_FILE)}\n")
        verify(report)
        print(report.render())
        if report.failed():
            print("\nFAILED - the library no longer matches its lock. Either restore the "
                  "assets or re-run the gate and re-lock.")
            return 1
        print("\nThe library matches its lock.")
        return 0

    print(f"PHASE 6 gate - {REPO}\n")
    state = run_gate(report)
    print(report.render())
    counts = report.counts()

    if report.failed():
        print(f"\nGATE FAILED - {counts.get(FAIL, 0)} blocking problem(s). "
              "The image library is not production-locked, and PHASE 7 stays closed "
              "(PLAN.md - IMAGE PIPELINE GATE).")
        return 1

    total = len(all_entries(state))
    print(f"\nGATE PASSED - {total} assets meet ASSET_SPEC and carry a human sign-off.")

    if not args.lock:
        print("Re-run with --lock --by \"name\" to write the production lock.")
        return 0

    lock, mirrored = write_lock(state, args.by)
    print(f"\nLocked v{lock['lock_version']} at {lock['locked_at']} by {args.by}")
    print(f"  {rel(LOCK_FILE)}")
    print(f"  {rel(BASELINE_DOC)}")
    print(f"  {mirrored} metadata mirror(s) written to {rel(GENERATIONS)}")
    print("\nPHASE 6 passed. PHASE 7 is unblocked. Do not regenerate a locked asset "
          "without a reason; if you do, re-run the gate and re-lock.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
