# Atrium presentation template

**Applies to:** the July 30, 2026 presentation and every presentation created after
it.

**Do not apply to:** presentations dated July 9 or July 16, 2026. Those decks are
historical artifacts and must remain unchanged.

## Required first interaction

Before drafting slide content, ask:

> What is the presentation about, who is the audience, how long is the talk, and
> what decision or takeaway should the audience leave with?

Do not invent a topic or begin composing slides until the user answers. If an
existing dated presentation brief already supplies these facts, summarize the known
answers and ask the user to confirm or correct them before applying the template.

## Audience-first explanation

Assume the audience has no background in mixture-of-experts models, RNA-seq,
reconstruction loss, routing, or the project’s internal stage names.

- Lead with the plain-language question and why it matters.
- Define a technical term at first use, or replace it with ordinary language.
- Explain comparisons as “one general model” versus “specialized models” before
  introducing terms such as pooled, expert, or router.
- Translate metrics into direction and meaning. For example: “3.7% lower prediction
  error; lower is better.”
- Never make the audience decode experiment shorthand such as `A1500+B750`.
  Describe the sample allocation in words and keep shorthand only as a small
  reproducibility label.
- Use one conclusion per slide and write headlines as takeaways, not topic labels.
- Keep protocol hashes, implementation commits, and debugging detail out of the main
  slide body. Put them in the scientific documentation.

## Theme

Use the **Atrium** theme throughout the complete deck.

### Color system

| Token | Hex | Use |
| --- | --- | --- |
| Warm cream | `#F7F2E9` | page and slide background |
| Sage green | `#7A8C6F` | primary fills, positive/supporting data, arch motifs |
| Terracotta | `#C4704F` | emphasis, italic headline word, kickers, comparison data |
| Soft sand | `#EFE7D8` | panels, tracks, subtle background fields |
| Deep olive ink | `#33392B` | all primary text and axes |

Never use pure white, pure black, neon colors, or highly saturated accents. Any
additional color must be muted and subordinate to this palette.

### Typography

- Headlines: **Fraunces**.
- Every main slide headline contains exactly one italic word in terracotta.
- Body, labels, and kickers: **Work Sans**.
- Kickers are small, uppercase, terracotta, and widely letter-spaced.
- No center-content text may be smaller than **14 px** at the normal 16:9 browser
  viewport. Body copy should normally be 19–22 px, chart labels at least 15 px after
  scaling, and result numbers substantially larger.
- Use tabular figures for quantitative values where available.
- Keep body copy short enough to read comfortably from the back of a room.

Load both fonts from Google Fonts when the output format supports web fonts. Provide
serif and sans-serif fallbacks for offline viewing.

### Signature arch

The signature form has a fully rounded top and square bottom. Use it for:

- photographs or simple illustration areas;
- portrait frames;
- number tokens;
- vertical bars, whose tops should read like arch windows.

Behind each filled arch, place a thin terracotta outline arch offset by approximately
4–6 pixels. The outline is an echo, not a heavy border.

Do not place dense data plots, heatmaps, or figures with embedded text inside an arch
or window-like frame. Present those figures without decorative borders and make them
large enough that their internal labels remain legible.

Do not place a recurring decorative arch trio in a corner. Every visible arch must
carry a function: framing data or imagery, identifying a slide number, or encoding a
quantity. If an ornament does not convey information or organize the composition,
remove it.

### Lines, panels, and composition

- Rules are one-pixel deep-olive lines at low opacity.
- Compositions are asymmetric but visually balanced.
- Use the canvas efficiently. Default slide padding should be approximately
  `28–34px 3vw`, with central content allowed to occupy about 92–94% of the slide
  width. Do not surround a small center block with a large unused perimeter.
- Preserve deliberate whitespace *between* content groups, but do not confuse
  oversized outer margins with clarity.
- Let the primary figure or result use up to roughly 68–74% of slide height when it
  remains legible.
- Prefer one dominant idea, result, or graphic per slide.
- Imagery and data frames must not have sharp top corners.
- Avoid dense card grids, excessive borders, and dashboard-like layouts.

### Slide transition

- Keyboard navigation uses an explicit **180 ms** ease-in-out transition between
  slides.
- Keep this duration consistent across the deck; do not depend on the browser's
  unspecified native smooth-scroll timing.
- Respect `prefers-reduced-motion` by moving immediately when reduced motion is
  requested.
- Arrow keys, Page Up/Down, and Space must remain supported.

### Pagination

- Use one centered row of small dots at the bottom of the viewport.
- Show one dot per slide.
- The current slide is larger or darker in deep olive; inactive slides remain muted
  sage/sand.
- Do not show a bottom-right page-number token.
- Keep the dots outside the main content region and update them during animated,
  keyboard, and direct-dot navigation.

### Charts

- Prefer a visual explanation whenever a chart, diagram, annotated comparison, or
  small table communicates the point faster than prose.
- Prioritize visuals for experimental design, quantitative results, comparisons,
  trends, uncertainty, and next-step decision trees.
- Do not add decoration merely to satisfy a visual quota. Every visual must clarify
  a relationship, magnitude, sequence, or decision.
- Use sage for the primary series and terracotta for the comparison or interference
  series.
- Use soft sand for tracks, reference bands, and neutral areas.
- Use deep olive for axes and labels; keep grid lines low-opacity.
- Bars have fully rounded arch-like tops.
- Label important values directly when possible.
- When importing a raster chart, allocate enough slide width for its embedded labels
  to remain readable; do not shrink a chart merely to preserve a large text column.
- Prefer a chart-dominant split of roughly 70–76% visual width on result slides,
  and allow those slides to use a wider content canvas than text-led slides.
- Remove decorative frames, rounded windows, and outline echoes from dense plots.
- Do not rely on color alone: retain signs, values, intervals, or concise labels.
- Preserve scientific uncertainty and claim boundaries; visual polish must not
  promote exploratory results into confirmed findings.

## Biweekly scientific narrative

Biweekly updates use a strict **plan → results → next** structure:

1. **Plan/question — 10–15% of the deck.** State the scientific question, frozen
   comparison, and what was completed.
2. **Results — 60–70% of the deck.** Give the main quantitative findings the most
   space. Show robustness, controls, uncertainty, and the bounded interpretation.
3. **Next — 15–20% of the deck.** State the decision implied by the results, the
   immediate experiment, and the criterion for continuing or pivoting.

Do not narrate implementation or failure history as “tried A, failed; tried B,
failed; finally C worked.” If a failure changes the scientific interpretation,
cohort, or evidence label, disclose it once in a concise sentence beside the
relevant result. Put debugging chronology, rejected alternatives, and technical
incident details in canonical scientific documentation, backup slides, or Q&A.

Prefer:

> Here was the plan. Here is what was completed. Here are the results and controls.
> Here is what they justify doing next.

The result section should be the largest portion of a biweekly deck.

## No talking scripts

Do not create presenter scripts, timed narration, or slide-by-slide prose intended to
be read aloud. The maintained presentation package consists of:

- the rendered deck;
- a concise content brief containing the slide purpose, essential facts, and visual
  direction; and
- a readiness checklist containing numeric and claim verification.

The slides must be understandable without a script. Delete obsolete script files
rather than carrying them forward. Put evidence verification in the readiness
checklist and detailed technical context in canonical scientific documentation, not
in a parallel narration document.

## Slide-level checklist

For every slide:

1. Use the warm-cream background and Atrium type system.
2. Give the main headline exactly one italic terracotta word.
3. Use at most one primary visual hierarchy.
4. Use the arch motif only when it has a framing, navigational, or quantitative
   function.
5. Fill the central canvas without oversized perimeter whitespace; retain breathing
   room between content groups.
6. Verify that no pure white, pure black, neon, saturated, or sharp-cornered imagery
   remains.
7. Verify the 180 ms transition and reduced-motion behavior.
8. For biweekly decks, verify that results occupy most of the presentation and that
   failure chronology is not part of the main narrative.
9. Verify that a nontechnical audience can understand every headline, metric, and
   comparison without project-specific background.
10. Confirm that center-content text is at least 14 px and imported-chart labels
    remain readable at presentation scale.
11. Verify centered pagination dots and the active-slide state.
12. Ask whether a visual would communicate the slide more clearly than prose.
13. Confirm that no talking script or timed narration file was created.
14. Check legibility at 16:9 presentation scale and in exported print/PDF output.

## Scientific presentation safeguard

Theme changes may alter layout and visual treatment, but must not change numerical
results, evidence labels, uncertainty, cohort definitions, protocol hashes, or claim
boundaries. Any substantive content update belongs in the dated presentation brief
before it is rendered into slides.
