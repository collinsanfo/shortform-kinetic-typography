# Tool adapters

Use an available editor or renderer that can execute the design. A paid generation service is not required. Inspect the existing project before replacing its stack.

## Layer-based editors

In an editor such as After Effects, Premiere or Resolve/Fusion, create separate display/support text layers, deliberate baselines, and explicit background/type/subject/foreground ordering. Group elements that should move together. For perspective, use a surface/corner transform and tracking when the camera or surface moves. Review the complete affected interval for matte and tracking defects.

Exact interfaces, expressions and capabilities change. Check current official documentation when implementation details are uncertain; do not invent menu paths or claim that a saved project is a finished render.

## Consumer editors

Reproduce hierarchy and readable placement first. Use masks, grouping and keyframes that are actually supported. If precise tracking or subject occlusion is unavailable, choose a good adjacent-word treatment instead of promising an effect the tool cannot produce. Check font substitution in the exported result and on another device if relevant.

## Code renderers

Use a frame-based renderer, canvas/SVG pipeline or compositor when reproducibility and variants matter. Derive frames from one timeline. Cache complete shaped word images or paths, then animate transforms and layers rather than reconstructing letters every frame.

Preserve these invariants:

- Include italic overhang and strokes in sprite bounds.
- Shape full words/lines before transforms.
- Transform a perspective plane coherently, not each letter independently.
- Keep the layer order explicit.
- Check transformed bounds after camera and perspective, not only source rectangles.
- Fit entrances, holds and exits into measured time.

The bundled Pillow tool previews still compositions. It does not animate a finished film, track a moving surface, generate subject mattes, or synthesize a voice. Translate its plan into the production renderer and inspect motion separately.

## Browser tools and connectors

Prefer relevant connected capabilities when sufficient. Respect the user's browser and interaction constraints and existing authorization. Typography work does not automatically authorize purchases, publication, external messages or unrelated account changes. If a tool lacks a necessary operation, explain the specific limit and use an appropriate available route within scope.

Generative media can supply source footage, but exact spelling, glyph shape and frame timing are usually better handled with controllable text layers. Reuse local assets for the visual text when practical.
