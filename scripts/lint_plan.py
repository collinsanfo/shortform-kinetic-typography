#!/usr/bin/env python3
"""Validate a version-1 typography plan using only the Python standard library.

Exit codes: 0 pass, 1 validation failure (including --strict warnings),
2 unreadable/invalid JSON input or report output error. Paths are relative to
the plan's directory. Colour values use CSS-style hexadecimal notation.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import sys
import unicodedata


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def tokens(text):
    """Ignore case, punctuation and curly-vs-straight apostrophes, not words."""
    value = unicodedata.normalize("NFKC", text).casefold()
    value = value.replace("\u2019", "'").replace("\u2018", "'").replace("'", "")
    return re.findall(r"[^\W_]+", value, flags=re.UNICODE)


def colour(value):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{3,4}(?:[0-9a-fA-F]{3,4})?", value):
        return None
    raw = value[1:]
    if len(raw) not in (3, 4, 6, 8):
        return None
    if len(raw) in (3, 4):
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) == 6:
        raw += "ff"
    return tuple(int(raw[index:index + 2], 16) for index in range(0, 8, 2))


def contrast(foreground, background):
    # Alpha-composite on the canvas colour. Images and local surfaces can change
    # the actual contrast; this intentionally remains a conservative heuristic.
    alpha = foreground[3] / 255
    rgb = [(foreground[i] * alpha + background[i] * (1 - alpha)) / 255 for i in range(3)]
    back = [channel / 255 for channel in background[:3]]
    def luminance(values):
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in values]
        return sum(c * weight for c, weight in zip(linear, (.2126, .7152, .0722)))
    a, b = sorted((luminance(rgb), luminance(back)))
    return (b + .05) / (a + .05)


def resolve_asset(plan_path, value):
    return (Path(plan_path).resolve().parent / value).resolve()


def reading_indices(shot):
    return shot.get("reading_order", list(range(len(shot.get("parts", [])))))


def validate(plan, plan_path, strict=False):
    report = {"version": 1, "plan": str(Path(plan_path).resolve()), "strict": strict,
              "valid": False, "errors": [], "warnings": [], "stats": {}}
    def issue(level, code, message, shot=None, part=None):
        entry = {"code": code, "message": message}
        if shot is not None:
            entry["shot"] = shot
        if part is not None:
            entry["part"] = part
        report[level].append(entry)
    def error(code, message, shot=None, part=None):
        issue("errors", code, message, shot, part)
    def warn(code, message, shot=None, part=None):
        issue("warnings", code, message, shot, part)
    def rect(value, label, shot=None, part=None):
        if not isinstance(value, list) or len(value) != 4 or not all(finite(v) for v in value):
            error("geometry", f"{label} must contain four finite numbers.", shot, part)
            return None
        if not all(0 <= v <= 1 for v in value) or value[0] >= value[2] or value[1] >= value[3]:
            error("geometry", f"{label} must be a nonempty normalized [left, top, right, bottom] rectangle.", shot, part)
            return None
        return value
    def path(value, label, shot=None):
        if not isinstance(value, str) or not value.strip():
            error("asset_path", f"{label} must be a nonempty file path.", shot)
            return False
        try:
            exists = resolve_asset(plan_path, value).is_file()
        except (OSError, ValueError):
            exists = False
        if not exists:
            error("asset_missing", f"{label} does not exist relative to the plan: {value}", shot)
        return exists
    if not isinstance(plan, dict):
        error("schema", "Plan must be a JSON object.")
        return report
    if type(plan.get("version")) is not int or plan["version"] != 1:
        error("version", "version must be 1.")
    canvas = plan.get("canvas")
    safe = None
    background = None
    if not isinstance(canvas, dict):
        error("canvas", "canvas must be an object.")
    else:
        for name in ("width", "height"):
            value = canvas.get(name)
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 8192:
                error("canvas", f"canvas.{name} must be an integer from 1 through 8192.")
        safe = rect(canvas.get("safe_rect"), "canvas.safe_rect")
        background = colour(canvas.get("background"))
        if background is None or background[3] != 255:
            error("colour", "canvas.background must be an opaque hexadecimal colour.")
    fonts = plan.get("fonts")
    if not isinstance(fonts, dict) or not fonts:
        error("fonts", "fonts must map one or more aliases to font file paths.")
        fonts = {}
    else:
        for alias, value in fonts.items():
            if not isinstance(alias, str) or not alias:
                error("fonts", "Font aliases must be nonempty strings.")
            path(value, f"Font {alias!r}")
    shots = plan.get("shots")
    if not isinstance(shots, list) or not shots:
        error("shots", "shots must contain one or more shots.")
        return report
    ids = set()
    valid_intervals = []
    used_families = set()
    part_count = 0
    for index, shot in enumerate(shots):
        if not isinstance(shot, dict):
            error("shot", f"Shot at index {index} must be an object.")
            continue
        sid = shot.get("id", f"index:{index}")
        if not isinstance(sid, str) or not sid or sid in ids:
            error("shot_id", "Each shot needs a unique nonempty string id.", str(sid))
        if isinstance(sid, str):
            ids.add(sid)
        start, end = shot.get("start"), shot.get("end")
        duration = None
        if not finite(start) or not finite(end) or start < 0 or end <= start:
            error("shot_timing", "Shot start/end must be finite, with 0 <= start < end.", sid)
        else:
            duration = end - start
            valid_intervals.append((start, end, str(sid)))
        source = shot.get("source_text")
        if not isinstance(source, str) or not tokens(source):
            error("source_text", "source_text must contain words.", sid)
        if shot.get("preserve_text") is not True:
            error("preserve_text", "preserve_text must be true; decorative repeats are the explicit exception.", sid)
        parts = shot.get("parts")
        if not isinstance(parts, list) or not parts:
            error("parts", "Each shot needs one or more parts.", sid)
            continue
        order = shot.get("reading_order", list(range(len(parts))))
        if (not isinstance(order, list) or any(not isinstance(v, int) or isinstance(v, bool) for v in order)
                or sorted(order) != list(range(len(parts)))):
            error("reading_order", "reading_order must be a permutation of all zero-based part indices.", sid)
            order = list(range(len(parts)))
        phrase = []
        hero_sizes, other_sizes = [], []
        actual_words = 0
        for pi in order:
            part = parts[pi]
            part_count += 1
            if not isinstance(part, dict):
                error("part", "Each part must be an object.", sid, pi)
                continue
            text = part.get("text")
            if not isinstance(text, str) or not text.strip():
                error("part_text", "Part text must be a nonempty string.", sid, pi)
            elif not part.get("decorative_repeat", False):
                phrase.append(text)
                actual_words += len(tokens(text))
            if "decorative_repeat" in part and not isinstance(part["decorative_repeat"], bool):
                error("decorative_repeat", "decorative_repeat must be a boolean.", sid, pi)
            role = part.get("role")
            if role not in ("hero", "support", "accent"):
                error("role", "Part role must be hero, support or accent.", sid, pi)
            alias = part.get("font")
            if not isinstance(alias, str) or alias not in fonts:
                error("font_alias", "Part font must name an alias from fonts.", sid, pi)
            elif isinstance(fonts[alias], str):
                stem = Path(fonts[alias]).stem.casefold()
                family = re.sub(r"(?:regular|italic|static|bold|semibold|medium|light|black|thin|\d+|[-_\s])", "", stem)
                used_families.add(family)
            size = part.get("size")
            if not finite(size) or not 0 < size <= 1:
                error("font_size", "size must be a fraction of canvas height in (0, 1].", sid, pi)
            elif not part.get("decorative_repeat", False):
                (hero_sizes if role == "hero" else other_sizes).append(size)
            box = rect(part.get("rect"), "Part rect", sid, pi)
            if box and safe and (box[0] < safe[0] or box[1] < safe[1] or box[2] > safe[2] or box[3] > safe[3]):
                warn("unsafe_rect", "Part rect extends outside the plan's safe_rect (a design heuristic, not an official platform safe zone).", sid, pi)
            fill = colour(part.get("color"))
            if fill is None:
                error("colour", "Part color must use hexadecimal notation.", sid, pi)
            outline = part.get("outline")
            stroke = None
            if outline is not None:
                if (not isinstance(outline, dict) or not finite(outline.get("width_px"))
                        or outline["width_px"] < 0 or outline["width_px"] > 512
                        or colour(outline.get("color")) is None):
                    error("outline", "outline needs width_px from 0 through 512 and a hexadecimal color.", sid, pi)
                elif outline["width_px"] > 0:
                    stroke = colour(outline["color"])
            if fill and background and contrast(fill, background) < 3 and (not stroke or contrast(stroke, background) < 3):
                warn("low_contrast", "Text/canvas contrast is below 3:1; local images or surfaces may change actual contrast.", sid, pi)
            pin, pout = part.get("in"), part.get("out")
            valid_part_time = finite(pin) and finite(pout) and 0 <= pin < pout
            if not valid_part_time or (duration is not None and pout > duration + 1e-9):
                error("part_timing", "Part in/out must satisfy 0 <= in < out <= shot duration.", sid, pi)
            elif isinstance(text, str) and not part.get("decorative_repeat", False):
                required = max(.45, len(tokens(text)) / 3)
                if pout - pin < required:
                    warn("brief_reading_hold", f"Visible for {pout - pin:.2f}s; a rough 180-word/minute reading heuristic suggests at least {required:.2f}s.", sid, pi)
            rotation = part.get("rotate_deg", 0)
            if not finite(rotation):
                error("rotation", "rotate_deg must be finite.", sid, pi)
            quad = part.get("quad")
            if quad is not None:
                valid_quad = (isinstance(quad, list) and len(quad) == 4
                              and all(isinstance(p, list) and len(p) == 2 and all(finite(v) and 0 <= v <= 1 for v in p) for p in quad))
                if valid_quad:
                    crosses = []
                    for qi in range(4):
                        a, b, c = quad[qi], quad[(qi + 1) % 4], quad[(qi + 2) % 4]
                        crosses.append((b[0]-a[0])*(c[1]-b[1]) - (b[1]-a[1])*(c[0]-b[0]))
                    valid_quad = all(v > 1e-8 for v in crosses) or all(v < -1e-8 for v in crosses)
                if not valid_quad:
                    error("quad", "quad needs four normalized, nondegenerate convex corners in TL, TR, BR, BL correspondence order.", sid, pi)
                elif safe and any(p[0] < safe[0] or p[0] > safe[2] or p[1] < safe[1] or p[1] > safe[3] for p in quad):
                    warn("unsafe_quad", "Perspective quad extends outside the plan's safe_rect.", sid, pi)
            motion = part.get("motion")
            if motion is not None:
                if not isinstance(motion, dict) or not isinstance(motion.get("kind"), str) or not motion["kind"].strip():
                    error("motion", "motion needs a nonempty kind and finite positive duration.", sid, pi)
                elif (not finite(motion.get("duration")) or motion["duration"] <= 0
                      or (valid_part_time and motion["duration"] > pout - pin + 1e-9)):
                    error("motion_duration", "motion.duration must be positive and no longer than the part's visible interval.", sid, pi)
        if isinstance(source, str) and tokens(" ".join(phrase)) != tokens(source):
            error("text_mutation", "Parts in reading order must preserve source_text words and order, excluding decorative_repeat parts.", sid)
        if not hero_sizes:
            warn("missing_hero", "No nondecorative hero part establishes a large-word hierarchy.", sid)
        elif other_sizes and max(hero_sizes) / max(other_sizes) < 1.5:
            warn("weak_hero_ratio", "Largest hero/support-or-accent size ratio is below 1.5; hierarchy may be weak.", sid)
        if duration is not None and actual_words / 3 > duration:
            warn("brief_shot_hold", f"{actual_words} words in {duration:.2f}s exceeds the rough 180-word/minute reading heuristic.", sid)
        images = shot.get("images", [])
        if not isinstance(images, list):
            error("images", "images must be an array.", sid)
        else:
            for ii, item in enumerate(images):
                if not isinstance(item, dict):
                    error("image", f"Image {ii} must be an object.", sid)
                    continue
                path(item.get("path"), f"Image {ii}", sid)
                rect(item.get("rect"), f"Image {ii} rect", sid)
                if item.get("plane") not in ("background", "subject", "foreground"):
                    error("image_plane", "Image plane must be background, subject or foreground.", sid)
        for pi, part in enumerate(parts):
            if isinstance(part, dict) and part.get("plane") not in ("background", "surface", "foreground"):
                error("part_plane", "Part plane must be background, surface or foreground.", sid, pi)
    ordered = sorted(valid_intervals)
    if [interval[0] for interval in valid_intervals] != [interval[0] for interval in ordered]:
        error("shot_order", "shots must be ordered by global start time.")
    for previous, current in zip(ordered, ordered[1:]):
        if current[0] < previous[1] - 1e-9:
            error("shot_overlap", f"Shot overlaps {previous[2]!r}.", current[2])
    if len(used_families) > 2:
        warn("too_many_families", f"Approximately {len(used_families)} font families are used; consider limiting to two. Filename-based heuristic.")
    report["stats"] = {"shots": len(shots), "parts": part_count, "font_families_estimate": len(used_families),
                       "duration_seconds": max((item[1] for item in valid_intervals), default=0)}
    report["valid"] = not report["errors"] and (not strict or not report["warnings"])
    return report


def load_plan(path):
    with Path(path).open("r", encoding="utf-8-sig") as handle:
        return json.load(handle, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"Nonfinite JSON value: {value}")))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--strict", action="store_true", help="Treat heuristic warnings as failures.")
    parser.add_argument("--output", type=Path, help="Write JSON report; otherwise print JSON to stdout.")
    args = parser.parse_args(argv)
    try:
        report = validate(load_plan(args.plan), args.plan, args.strict)
        status = 0 if report["valid"] else 1
    except (OSError, ValueError) as exc:
        report = {"version": 1, "plan": str(args.plan.resolve()), "valid": False,
                  "errors": [{"code": "input_error", "message": str(exc)}], "warnings": []}
        status = 2
    payload = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"Cannot write report: {exc}", file=sys.stderr)
            return 2
        print(f"{'PASS' if status == 0 else 'FAIL'}: {len(report['errors'])} errors, {len(report['warnings'])} warnings; {args.output}")
    else:
        print(payload)
    return status


if __name__ == "__main__":
    sys.exit(main())
