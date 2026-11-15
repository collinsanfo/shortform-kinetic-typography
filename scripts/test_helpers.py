"""Offline regression tests: python scripts/test_helpers.py -v."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw

from lint_plan import load_plan, resolve_asset, tokens, validate
from render_preview import make_text_layer, perspective_coefficients, render_shot


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "assets" / "example-plan.json"


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.plan = load_plan(EXAMPLE)

    def codes(self, plan):
        return {item["code"] for item in validate(plan, EXAMPLE)["errors"]}

    def cli(self, script, *args):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / script), *map(str, args)],
                              capture_output=True, text=True, encoding="utf-8", timeout=45)

    def test_demo_is_strictly_valid_and_uses_real_fonts(self):
        report = validate(self.plan, EXAMPLE, strict=True)
        self.assertTrue(report["valid"], report)
        self.assertEqual(report["stats"]["duration_seconds"], 12)
        for font in self.plan["fonts"].values():
            self.assertTrue(resolve_asset(EXAMPLE, font).is_file())

    def test_text_normalization_and_decorative_repeat(self):
        self.assertEqual(tokens("Don’t STOP—now!"), tokens("DON'T stop, now."))
        shot = self.plan["shots"][0]
        duplicate = deepcopy(shot["parts"][1])
        duplicate["decorative_repeat"] = True
        shot["parts"].append(duplicate)
        self.assertNotIn("text_mutation", self.codes(self.plan))
        del duplicate["decorative_repeat"]
        self.assertIn("text_mutation", self.codes(self.plan))

    def test_detects_word_mutation_and_order_changes(self):
        self.plan["shots"][0]["parts"][1]["text"] = "POSSIBLE"
        self.assertIn("text_mutation", self.codes(self.plan))
        self.plan = load_plan(EXAMPLE)
        shot = self.plan["shots"][0]
        shot["parts"][0], shot["parts"][1] = shot["parts"][1], shot["parts"][0]
        self.assertIn("text_mutation", self.codes(self.plan))
        shot["reading_order"] = [1, 0, 2]
        self.assertNotIn("text_mutation", self.codes(self.plan))

    def test_detects_invalid_timeline_out_and_motion_duration(self):
        self.plan["shots"][1]["start"] = 3
        self.plan["shots"][0]["parts"][0]["out"] = 7
        self.plan["shots"][0]["parts"][1]["motion"]["duration"] = 10
        self.assertTrue({"shot_overlap", "part_timing", "motion_duration"}.issubset(self.codes(self.plan)))

    def test_detects_nonfinite_geometry_and_degenerate_quad(self):
        self.plan["shots"][0]["parts"][0]["rect"][0] = float("nan")
        self.plan["shots"][1]["parts"][2]["quad"] = [[.1, .1]] * 4
        self.assertTrue({"geometry", "quad"}.issubset(self.codes(self.plan)))
        self.plan = load_plan(EXAMPLE)
        self.plan["shots"][0]["parts"][0]["rect"][0] = -.1
        self.assertIn("geometry", self.codes(self.plan))

    def test_missing_fonts_and_required_parts_fail(self):
        self.plan["fonts"]["display"] = "fonts/nonexistent.ttf"
        self.plan["shots"][0]["parts"] = []
        self.assertTrue({"asset_missing", "parts"}.issubset(self.codes(self.plan)))
        self.plan = load_plan(EXAMPLE)
        self.plan["shots"][0]["images"] = [{"path": "does-not-exist.png", "rect": [0, 0, 1, 1], "plane": "subject"}]
        self.assertIn("asset_missing", self.codes(self.plan))

    def test_strict_promotes_design_warnings(self):
        self.plan["shots"][0]["parts"][0]["color"] = "#111827"
        loose = validate(self.plan, EXAMPLE)
        strict = validate(self.plan, EXAMPLE, strict=True)
        self.assertTrue(loose["valid"])
        self.assertFalse(strict["valid"])
        self.assertIn("low_contrast", {item["code"] for item in strict["warnings"]})

    def test_real_italic_and_outline_glyph_bounds_have_transparent_margin(self):
        for shot in self.plan["shots"]:
            for part in shot["parts"]:
                layer, info = make_text_layer(part, self.plan, EXAMPLE)
                self.assertEqual(info["requested_font_px"], info["actual_font_px"])
                left, top, right, bottom = info["source_glyph_bounds_px"]
                box = info["rect_px"]
                self.assertGreater(left, 0)
                self.assertGreater(top, 0)
                self.assertLess(right, box[2] - box[0])
                self.assertLess(bottom, box[3] - box[1])
                self.assertIsNotNone(layer.getchannel("A").getbbox())
                self.assertFalse(info["warnings"], info)

    def test_oversize_text_reports_reduction_and_preserves_bounds(self):
        part = self.plan["shots"][0]["parts"][1]
        part["size"] = .5
        _, info = make_text_layer(part, self.plan, EXAMPLE)
        self.assertLess(info["actual_font_px"], info["requested_font_px"])
        self.assertIn("font_size_reduced", {item["code"] for item in info["warnings"]})

    def test_perspective_maps_each_corner(self):
        destination = [(20, 30), (160, 10), (170, 130), (10, 120)]
        source = [(0, 0), (200, 0), (200, 100), (0, 100)]
        a, b, c, d, e, f, g, h = perspective_coefficients(destination, source)
        for (x, y), (u, v) in zip(destination, source):
            self.assertAlmostEqual((a*x+b*y+c)/(g*x+h*y+1), u, places=7)
            self.assertAlmostEqual((d*x+e*y+f)/(g*x+h*y+1), v, places=7)

    def test_time_hides_parts_until_their_in_point(self):
        _, info = render_shot(self.plan, EXAMPLE, self.plan["shots"][0], 0)
        self.assertEqual(info["hidden_part_indices"], [1, 2])

    def test_alpha_image_and_foreground_plane_are_actually_composited(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.png"
            fixture = Image.new("RGBA", (100, 100))
            ImageDraw.Draw(fixture).rectangle((20, 20, 79, 79), fill=(255, 0, 0, 128))
            fixture.save(path)
            shot = self.plan["shots"][0]
            baseline, _ = render_shot(self.plan, EXAMPLE, shot, 2)
            shot["images"] = [{"path": str(path), "rect": [0, 0, 1, 1], "plane": "foreground"}]
            frame, info = render_shot(self.plan, EXAMPLE, shot, 2)
            self.assertEqual(frame.getpixel((0, 0)), baseline.getpixel((0, 0)))
            # Contain keeps the square at the centre of the portrait canvas.
            point = (540, 800)
            before, after = baseline.getpixel(point), frame.getpixel(point)
            self.assertNotEqual(before, after)
            self.assertAlmostEqual(after[0], round(before[0] * 127/255 + 128), delta=1)
            self.assertAlmostEqual(after[1], round(before[1] * 127/255), delta=1)
            ordered = [(item["kind"], item["index"]) for item in info["elements"]]
            self.assertGreater(ordered.index(("image", 0)), ordered.index(("text", 1)))

    def test_cli_exit_codes_reports_and_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            report = directory / "lint.json"
            passed = self.cli("lint_plan.py", EXAMPLE, "--strict", "--output", report)
            self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
            self.assertTrue(json.loads(report.read_text(encoding="utf-8"))["valid"])
            broken = directory / "broken.json"
            broken.write_text('{"bad": NaN}', encoding="utf-8")
            self.assertEqual(self.cli("lint_plan.py", broken).returncode, 2)
            mutated = deepcopy(self.plan)
            mutated["fonts"] = {alias: str(resolve_asset(EXAMPLE, path)) for alias, path in mutated["fonts"].items()}
            mutated["shots"][0]["parts"][0]["text"] = "Changed words"
            broken.write_text(json.dumps(mutated), encoding="utf-8")
            self.assertEqual(self.cli("lint_plan.py", broken).returncode, 1)
            output = directory / "snapshot.png"
            rendered = self.cli("render_preview.py", EXAMPLE, "--shot", "perspective", "--time", "6", "--output", output, "--strict")
            self.assertEqual(rendered.returncode, 0, rendered.stdout + rendered.stderr)
            with Image.open(output) as image:
                self.assertEqual(image.size, (1080, 1920))
            layout = json.loads(output.with_suffix(".layout.json").read_text(encoding="utf-8"))
            self.assertEqual(layout["warning_count"], 0)
            self.assertTrue(any(element.get("quad_applied") for element in layout["frames"][0]["elements"]))


if __name__ == "__main__":
    unittest.main()
