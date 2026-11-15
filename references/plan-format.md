# Portable composition plan, version 1

The plan supports deterministic still previews and basic validation. It is editor-neutral: a production renderer must translate the plan into motion and final media. Motion metadata is checked, not animated by the Pillow helper.

## Root fields

| Field | Meaning |
|---|---|
| `version` | Integer `1` |
| `canvas.width`, `height` | Integer pixel dimensions from 1 through 8192 |
| `canvas.background` | Opaque hexadecimal background colour |
| `canvas.safe_rect` | Normalized `[left, top, right, bottom]` |
| `fonts` | Alias-to-font-file mapping; paths relative to the plan file |
| `shots` | Ordered, non-overlapping timed compositions |

Coordinates run from 0 to 1 across the full canvas. Font `size` is a fraction of canvas **height**, not width, in `(0, 1]`. Rectangles use edges, not `[x, y, width, height]`. Global shot times and shot-relative part times are in seconds. Colours use hexadecimal `#RGB`, `#RGBA`, `#RRGGBB` or `#RRGGBBAA` notation; alpha is supported on parts and outlines.

Safe rectangles are configurable editorial starting points, not an official platform specification. Verify current platform overlays and the actual delivery context. Important type may need more inset than background imagery.

## Shot fields

Each shot needs `id`, global `start`/`end`, `source_text`, `preserve_text`, and `parts`. Part array order is the default reading order. Optional `reading_order` is a permutation of zero-based part indices. It includes decorative parts, which are ignored in source-token comparison.

`preserve_text: true` checks the normalized source tokens against the non-decorative reading order. Case and punctuation normalization permit visual styling; missing, added or reordered words are content errors. This does not establish that the viewer will actually follow the visual ordering.

Optional `images` entries have `path`, `rect` and `plane`. Images must be local assets resolved relative to the plan. Use an alpha cutout for genuine subject occlusion; an opaque rectangular photograph hides the type behind its whole rectangle.

## Part fields

| Field | Meaning |
|---|---|
| `text` | Complete word or phrase to render |
| `role` | `hero`, `support`, or `accent` |
| `font` | Alias from the root font mapping |
| `size` | Fraction of canvas height |
| `rect` | Normalized text placement rectangle |
| `color` | Fill colour |
| `plane` | `background`, `surface`, or `foreground` |
| `in`, `out` | Visibility times relative to shot start |
| `decorative_repeat` | Optional `true` for an echo that is not new content |
| `outline` | Optional `{width_px, color}` |
| `rotate_deg` | Optional finite rotation in degrees; positive is clockwise |
| `quad` | Optional four normalized points: top-left, top-right, bottom-right, bottom-left |
| `motion` | Optional metadata, such as `{kind: "reveal", duration: 0.18}` |

Image planes are `background`, `subject` or `foreground`. Compositing proceeds through background, surface, subject and foreground. The background colour is drawn first. On a shared plane, images precede text; array order is retained within each type. Images use `contain` fitting and preserve alpha. A perspective quad should follow a real surface when used in footage; the helper only proves its static geometry. A quad maps the complete part rectangle to the four specified destination corners, including any rotation within the source rectangle.

## Helpers

```bash
python scripts/lint_plan.py assets/example-plan.json
python scripts/lint_plan.py assets/example-plan.json --strict --output report.json
python scripts/render_preview.py assets/example-plan.json --output contact.png
python scripts/render_preview.py assets/example-plan.json --shot perspective --output perspective.png
python scripts/render_preview.py assets/example-plan.json --time 1.5 --output moment.png
```

Run each script with `--help` for supported options. The linter distinguishes structural/content errors from editorial warnings. Strict mode promotes warnings; it does not turn a warning-free result into an aesthetic or accessibility certification.

The default preview is a contact sheet at each shot's midpoint (`--contact` is explicit). `--shot ID` renders one midpoint; `--time SECONDS` selects the active shot or a time within `--shot`. Shot ends and part `out` values are exclusive. `--contact` cannot be combined with `--time`. `--report PATH` overrides the default `OUTPUT.layout.json`; `--thumb-width` changes contact thumbnails. Preview `--strict` fails on validation or measured-layout warnings while still writing an otherwise successful render.

Linter exit codes: `0` passed, `1` invalid plan or strict-mode warning, `2` unreadable/invalid JSON input or report-output error. Preview exit codes: `0` rendered successfully, `1` validation/render failure or strict-mode warning, `2` invalid CLI/input or report-output error. Font decode failures are render errors. Preview reports include requested/actual font sizes, measured whole-glyph bounds, source rectangle bounds, applied quads and hidden parts. Canvas-safe rectangles, a 3:1 contrast threshold, a 1.5 hero-size ratio, filename-based family counting and roughly 180 words/minute are configurable-plan or editorial heuristics, not official delivery specifications or accessibility certification.

The preview uses real fonts and includes measured-fit reporting. Inspect any font-size reduction or overflow: automatic fitting may erase the intended hierarchy. The preview's time option selects active elements in their final static geometry; it is not an animation preview. It does not synthesize speech, generate mattes, track footage or export a film.

See `assets/example-plan.json` for executable, generic compositions with bundled font paths. Keep each plan's paths portable when packaging it for another machine.
