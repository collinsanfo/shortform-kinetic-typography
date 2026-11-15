#!/usr/bin/env python3
"""Render static plan snapshots/contact sheets with Pillow, without network jobs.

This is a layout preview, not a video renderer. Part in/out visibility is
honoured; motion metadata is not animated. Quads map each part's rect onto
four destination corners using a projective transform. No glyph is silently
clipped: requested-size reductions and measured bounds enter a JSON report.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont, ImageOps

from lint_plan import colour, finite, load_plan, resolve_asset, validate


PLANES = {"background": 0, "surface": 1, "subject": 2, "foreground": 3}


def solve_linear(matrix, values):
    """Small Gauss-Jordan solver with partial pivoting; no NumPy dependency."""
    size = len(values)
    rows = [list(map(float, row)) + [float(value)] for row, value in zip(matrix, values)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(rows[row][column]))
        if abs(rows[pivot][column]) < 1e-10:
            raise ValueError("Degenerate perspective quad.")
        rows[column], rows[pivot] = rows[pivot], rows[column]
        divisor = rows[column][column]
        rows[column] = [value / divisor for value in rows[column]]
        for row in range(size):
            if row != column:
                factor = rows[row][column]
                rows[row] = [a - factor * b for a, b in zip(rows[row], rows[column])]
    return [row[-1] for row in rows]


def perspective_coefficients(destination, source):
    """Pillow needs inverse coefficients mapping destination pixels to source."""
    matrix, values = [], []
    for (x, y), (u, v) in zip(destination, source):
        matrix.append([x, y, 1, 0, 0, 0, -u*x, -u*y])
        values.append(u)
        matrix.append([0, 0, 0, x, y, 1, -v*x, -v*y])
        values.append(v)
    return solve_linear(matrix, values)


def pixel_rect(rect, width, height):
    return (round(rect[0] * width), round(rect[1] * height),
            round(rect[2] * width), round(rect[3] * height))


def text_raster(text, font_path, font_px, fill, stroke_width=0, stroke_fill=None, rotation=0):
    font = ImageFont.truetype(str(font_path), font_px)
    draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    spacing = max(1, round(font_px * .12))
    bounds = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing,
                                    align="center", stroke_width=stroke_width)
    padding = max(3, stroke_width + 2)
    width = max(1, math.ceil(bounds[2] - bounds[0]) + padding * 2)
    height = max(1, math.ceil(bounds[3] - bounds[1]) + padding * 2)
    image = Image.new("RGBA", (width, height))
    ImageDraw.Draw(image).multiline_text((padding - bounds[0], padding - bounds[1]), text,
                                        font=font, fill=fill, spacing=spacing, align="center",
                                        stroke_width=stroke_width, stroke_fill=stroke_fill)
    if rotation:
        # Positive values rotate clockwise in this plan format.
        image = image.rotate(-rotation, resample=Image.Resampling.BICUBIC, expand=True)
    alpha_bounds = image.getchannel("A").getbbox()
    if alpha_bounds is None:
        raise ValueError("Text produced no visible pixels; check glyph support and colours.")
    # Keep two transparent pixels around the whole transformed glyph extent.
    cropped = image.crop(alpha_bounds)
    result = Image.new("RGBA", (cropped.width + 4, cropped.height + 4))
    result.alpha_composite(cropped, (2, 2))
    return result


def make_text_layer(part, plan, plan_path):
    width, height = plan["canvas"]["width"], plan["canvas"]["height"]
    left, top, right, bottom = pixel_rect(part["rect"], width, height)
    box_width, box_height = right - left, bottom - top
    if box_width < 5 or box_height < 5:
        raise ValueError("Part rect is too small in pixels to preserve complete glyph bounds.")
    requested_px = max(1, round(part["size"] * height))
    outline = part.get("outline", {})
    stroke = round(outline.get("width_px", 0))
    font_path = resolve_asset(plan_path, plan["fonts"][part["font"]])
    def raster(size):
        return text_raster(part["text"], font_path, size, colour(part["color"]), stroke,
                           colour(outline.get("color", part["color"])), part.get("rotate_deg", 0))
    glyphs = raster(requested_px)
    actual_px = requested_px
    if glyphs.width > box_width or glyphs.height > box_height:
        low, high, chosen = 1, requested_px - 1, None
        while low <= high:
            middle = (low + high) // 2
            candidate = raster(middle)
            if candidate.width <= box_width and candidate.height <= box_height:
                chosen = (middle, candidate)
                low = middle + 1
            else:
                high = middle - 1
        if chosen is None:
            raise ValueError("Text and outline cannot fit this rect even at a one-pixel font size.")
        actual_px, glyphs = chosen
    local = Image.new("RGBA", (box_width, box_height))
    local.alpha_composite(glyphs, ((box_width - glyphs.width) // 2, (box_height - glyphs.height) // 2))
    source_bounds = local.getchannel("A").getbbox()
    if source_bounds is None or source_bounds[0] <= 0 or source_bounds[1] <= 0 or source_bounds[2] >= box_width or source_bounds[3] >= box_height:
        raise ValueError("Glyph extent touches the source rect edge; increase the rect or reduce outline width.")
    layer = Image.new("RGBA", (width, height))
    if "quad" in part:
        quad = [(point[0] * width, point[1] * height) for point in part["quad"]]
        source = [(0, 0), (box_width, 0), (box_width, box_height), (0, box_height)]
        coefficients = perspective_coefficients(quad, source)
        layer = local.transform((width, height), Image.Transform.PERSPECTIVE,
                                coefficients, Image.Resampling.BICUBIC)
    else:
        layer.alpha_composite(local, (left, top))
    bounds = layer.getchannel("A").getbbox()
    warnings = []
    if actual_px < requested_px:
        warnings.append({"code": "font_size_reduced", "message": f"Font reduced from {requested_px}px to {actual_px}px to preserve complete glyph bounds."})
    safe = pixel_rect(plan["canvas"]["safe_rect"], width, height)
    if bounds and (bounds[0] < safe[0] or bounds[1] < safe[1] or bounds[2] > safe[2] or bounds[3] > safe[3]):
        warnings.append({"code": "measured_unsafe_bounds", "message": "Measured glyph pixels extend outside safe_rect."})
    if bounds is None:
        raise ValueError("Transformed text produced no visible pixels.")
    if bounds[0] == 0 or bounds[1] == 0 or bounds[2] == width or bounds[3] == height:
        warnings.append({"code": "canvas_edge_contact", "message": "Text touches the canvas edge; inspect possible transformed clipping."})
    return layer, {"text": part["text"], "requested_font_px": requested_px,
                   "actual_font_px": actual_px, "font_path": str(font_path),
                   "source_glyph_bounds_px": list(source_bounds), "bounds_px": list(bounds),
                   "rect_px": [left, top, right, bottom], "quad_applied": "quad" in part,
                   "warnings": warnings}


def make_image_layer(item, plan, plan_path):
    width, height = plan["canvas"]["width"], plan["canvas"]["height"]
    left, top, right, bottom = pixel_rect(item["rect"], width, height)
    if right <= left or bottom <= top:
        raise ValueError("Image rect is empty at the canvas pixel resolution.")
    asset = resolve_asset(plan_path, item["path"])
    with Image.open(asset) as opened:
        source = ImageOps.exif_transpose(opened).convert("RGBA")
        contained = ImageOps.contain(source, (right - left, bottom - top), Image.Resampling.LANCZOS)
    layer = Image.new("RGBA", (width, height))
    layer.alpha_composite(contained, (left + (right-left-contained.width)//2, top + (bottom-top-contained.height)//2))
    bounds = layer.getchannel("A").getbbox()
    return layer, {"path": str(asset), "bounds_px": list(bounds) if bounds else None,
                   "rect_px": [left, top, right, bottom], "fit": "contain", "warnings": []}


def render_shot(plan, plan_path, shot, global_time):
    width, height = plan["canvas"]["width"], plan["canvas"]["height"]
    canvas = Image.new("RGBA", (width, height), colour(plan["canvas"]["background"]))
    local_time = global_time - shot["start"]
    operations = []
    # Images precede text on a shared plane; array order is preserved within type.
    for index, item in enumerate(shot.get("images", [])):
        operations.append((PLANES[item["plane"]], 0, index, "image", item))
    for index, part in enumerate(shot["parts"]):
        if part["in"] <= local_time < part["out"]:
            operations.append((PLANES[part["plane"]], 1, index, "text", part))
    details = []
    for _, _, index, kind, item in sorted(operations, key=lambda op: op[:3]):
        layer, info = (make_text_layer(item, plan, plan_path) if kind == "text"
                       else make_image_layer(item, plan, plan_path))
        canvas.alpha_composite(layer)
        info.update({"kind": kind, "index": index, "plane": item["plane"]})
        details.append(info)
    return canvas, {"shot": shot["id"], "global_time": global_time, "local_time": local_time,
                    "elements": details,
                    "hidden_part_indices": [i for i, p in enumerate(shot["parts"]) if not p["in"] <= local_time < p["out"]]}


def contact_sheet(frames, thumbnail_width=360):
    columns = min(3, len(frames))
    scale = thumbnail_width / frames[0][0].width
    frame_height = round(frames[0][0].height * scale)
    label_height, gap = 36, 16
    rows = math.ceil(len(frames) / columns)
    sheet = Image.new("RGB", (columns * (thumbnail_width + gap) + gap,
                              rows * (frame_height + label_height + gap) + gap), "#22252b")
    draw = ImageDraw.Draw(sheet)
    for index, (frame, info) in enumerate(frames):
        x, y = gap + (index % columns) * (thumbnail_width + gap), gap + (index // columns) * (frame_height + label_height + gap)
        sheet.paste(frame.convert("RGB").resize((thumbnail_width, frame_height), Image.Resampling.LANCZOS), (x, y))
        draw.text((x, y + frame_height + 8), f"{info['shot']} | {info['global_time']:.2f}s", fill="white")
    return sheet


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output", required=True, type=Path, help="PNG, JPEG or WebP output path.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--shot", help="Render one shot at its midpoint, unless --time is supplied.")
    mode.add_argument("--contact", action="store_true", help="Render one midpoint per shot (the default).")
    parser.add_argument("--time", type=float, help="Global snapshot time; selects its active shot unless --shot is set.")
    parser.add_argument("--report", type=Path, help="Layout JSON path; defaults to OUTPUT.layout.json.")
    parser.add_argument("--strict", action="store_true", help="Fail on linter or measured layout warnings; still writes a successful render.")
    parser.add_argument("--thumb-width", type=int, default=360)
    args = parser.parse_args(argv)
    if args.contact and args.time is not None:
        parser.error("--contact and --time cannot be combined.")
    if args.thumb_width < 32 or args.thumb_width > 4096:
        parser.error("--thumb-width must be between 32 and 4096.")
    report_path = args.report or args.output.with_suffix(".layout.json")
    try:
        plan = load_plan(args.plan)
        lint = validate(plan, args.plan)
    except (OSError, ValueError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2
    if lint["errors"]:
        print(json.dumps(lint, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    if args.time is not None and (not finite(args.time) or args.time < 0):
        parser.error("--time must be finite and nonnegative.")
    shots = plan["shots"]
    if args.shot:
        shots = [shot for shot in shots if shot["id"] == args.shot]
        if not shots:
            parser.error(f"Unknown shot: {args.shot}")
    elif args.time is not None:
        shots = [shot for shot in shots if shot["start"] <= args.time < shot["end"]]
        if not shots:
            parser.error("No shot is active at --time (shot end is exclusive).")
    if args.time is not None and not shots[0]["start"] <= args.time < shots[0]["end"]:
        parser.error("--time is outside the selected shot (end is exclusive).")
    layout = {"version": 1, "plan": str(args.plan.resolve()), "output": str(args.output.resolve()),
              "mode": "snapshot" if args.shot or args.time is not None else "contact",
              "motion": "Static geometry; in/out visibility only. Motion metadata is not animated.",
              "plane_order": ["background", "surface", "subject", "foreground"],
              "validation_warnings": lint["warnings"], "frames": [], "errors": []}
    try:
        frames = []
        for shot in shots:
            time = args.time if args.time is not None else (shot["start"] + shot["end"]) / 2
            frame, info = render_shot(plan, args.plan, shot, time)
            frames.append((frame, info))
            layout["frames"].append(info)
        output = frames[0][0] if layout["mode"] == "snapshot" else contact_sheet(frames, args.thumb_width)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.output.suffix.lower() in (".jpg", ".jpeg"):
            output = output.convert("RGB")
        output.save(args.output)
    except (OSError, ValueError) as exc:
        layout["errors"].append({"code": "render_error", "message": str(exc)})
    warning_count = len(lint["warnings"]) + sum(len(e["warnings"]) for frame in layout["frames"] for e in frame["elements"])
    layout["warning_count"] = warning_count
    layout["valid"] = not layout["errors"] and (not args.strict or warning_count == 0)
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(layout, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"Cannot write layout report: {exc}", file=sys.stderr)
        return 2
    print(f"{'PASS' if layout['valid'] else 'FAIL'}: {len(layout['errors'])} errors, {warning_count} warnings; layout report: {report_path}")
    return 0 if layout["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
