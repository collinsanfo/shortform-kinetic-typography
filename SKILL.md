---
name: shortform-kinetic-typography
description: Compose expressive on-screen typography for short-form videos using strong word hierarchy, mixed scale, selective accents, subject overlap, and perspective. Use for reference-led text restyling or kinetic text sequences; ordinary subtitle transcription alone does not need this skill.
---

# Shortform Kinetic Typography

Turn a spoken thought into a deliberate visual composition. A good result has a clear reading order, meaningful emphasis, and text that belongs in the scene. Increasing every word's size or adding transitions to a uniform heading is insufficient.

## Identify the job

Distinguish **review**, **restyle**, and **rewrite plus restyle**. In a restyle, retain the wording and narration and change the typography, placement, layers and motion. Infer intent from the conversation; ask only when this distinction remains material and unresolved. A review-only request does not authorize a full production workflow.

Record the format, timeline, brand constraints and frozen assets. Preserve explicitly locked covers, logos, identity, copy and audio. Reuse good narration to solve a visual problem. User-specific preferences belong in the project brief, not universal skill rules.

## Read the reference

Inspect the actual images or clips. Describe observable hierarchy, type width/weight, contrast, line breaks, placement, occlusion and perspective. A screenshot does not prove animation timing, an exact font identity, or advertising performance. Proposed motion should be labelled as your design choice.

Read [design-recipes.md](references/design-recipes.md) to choose a small related set of treatments. The recipes are options, not a requirement to use every effect.

## Compose the phrases

1. Choose the semantic word or short phrase that deserves the largest scale; make the rest support it.
2. Establish reading order before positioning elements. Preserve the complete meaning despite line breaks, case changes and emphasis.
3. Try scale, weight and placement before adding colours or fonts. Use a coherent set of display, supporting and occasional accent roles.
4. Relate type to the picture when useful: behind a clean subject matte, beside a gesture, on a desk, or along a perspective surface. Protect faces and important product details.
5. Give related thoughts varied compositions. A constant top heading above a changing photograph still looks like a slide template.

Bundled Anton, heavy DM Sans and DM Sans italic are convenient starting points, not mandatory brand choices. Their separate OFL licences and hashes are in `assets/fonts/`.

## Time and build

Read [timing-production.md](references/timing-production.md) for measured speech anchors, readable holds, narration rhythm and efficient proofing. Energy can come from fast word entrances while the voice remains at its original pace. Budget for reading after the entrance and before the transition.

Use an existing project/editor when suitable. For portable still prototypes:

```bash
python scripts/lint_plan.py assets/example-plan.json
python scripts/render_preview.py assets/example-plan.json --output preview.png
```

Read [plan-format.md](references/plan-format.md) for the data contract. The preview helper renders compositions, not a finished animated video. [tool-adapters.md](references/tool-adapters.md) covers implementation choices.

Inspect representative full-size layouts and a short motion proof internally before a long export. Include a short phrase, long phrase, advanced layer effect and closing view when relevant. Fix actual defects; avoid repeated proof loops without a new reason. Routine internal QA is not a mandatory user approval gate.

## Deliver honestly

Use [qa-delivery.md](references/qa-delivery.md). Verify the final encoded file, not just drawing code or a contact sheet. Distinguish technical validation, sampled visual inspection, continuous viewing/listening and owner approval.

Deliver a usable result and editable sources when requested. Retain font licences in reusable packages. Exclude private recordings, credentials, customer data and unlicensed reference creators' media. An open-source package prepared locally is not a publicly published repository.

[examples.md](references/examples.md) provides reusable requests. Extend the recipes for demonstrated needs; keep conditional mechanics in references rather than loading everything for every task.
