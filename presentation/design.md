# Anthropic field-journal presentation design

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

## Design direction

Use an **Anthropic-inspired scientific field journal** throughout the complete
deck: quiet parchment surfaces, editorial serif typography, restrained sans-serif
UI labels, flat paper-like panels, hairline rules, and one clay accent used only for
the most consequential conclusion or action.

The previous Atrium language is retained only where it strengthens this direction:
an occasional functional arch may frame a number or simple image. Anthropic's
editorial system is the primary authority for color, type, surfaces, density, and
component treatment.

### Color system

| Token | Hex | Presentation use |
| --- | --- | --- |
| Slate Dark | `#141413` | primary text, headings, axes, and the only dark inversion |
| Ivory Medium | `#f0eee6` | slide canvas and page background |
| Ivory Light | `#faf9f5` | standard paper-card surface |
| Oat Warm | `#e3dacc` | grouped panels and deeper paper fields |
| Manilla | `#f5e3c7` | one featured editorial panel when hierarchy requires it |
| Stone | `#cccbc8` | hairline borders and dividers |
| Cloud Dark | `#87867f` | secondary labels and inactive pagination |
| Cloud Medium | `#b0aea5` | quiet helper text that is not presentation-critical |
| Slate Medium | `#3d3d3a` | secondary high-legibility text and neutral data |
| Clay | `#d97757` | single decisive accent or comparison |
| Clay Deep | `#c6613f` | active/pressed clay and stronger negative emphasis |
| Sage | `#7A8C6F` | primary positive or specialist data series |
| Soft Sage | `#91A087` | secondary specialist or blended-routing series |
| Muted Blue | `#798C91` | automatic-choice or alternate-method data series |
| Deep Sage | `#62785B` | strongest verified positive value |

Never use pure white, pure black, cool tech gray, neon, gradients, glows, or highly
saturated decorative colors. Use flat solid surfaces. Scientific plots may retain a
necessary diverging or categorical scale, but it must be muted, explained, and
subordinate to the editorial palette outside the data region.

The Atrium sage and muted blue are retained as **functional data accents**, not as
decorative surface colors. A typical ranked comparison may use neutral gray for the
baseline, Muted Blue for the numerical winner, Sage for a secondary specialist or
automatic method, and Soft Sage for a blended route. Do not apply all accents merely
because they are available.

### Typography

- Editorial family token: **Anthropic Serif**, weight 400 by default and 600 for
  emphasis. Use it for display headlines, body copy, card titles, and explanatory
  paragraphs.
- Interface family token: **Anthropic Sans**, weights 400–700. Use it only for
  kickers, navigation, labels, badges, axes, compact metadata, and a rare declarative
  sans headline.
- Technical family token: **Anthropic Mono**, weight 400. Reserve it for code,
  hashes, and reproducibility snippets; keep those out of the main slide body.
- Portable web implementation: `"Anthropic Serif", "Source Serif 4", Georgia,
  Charter, serif`; `"Anthropic Sans", Inter, system-ui, Arial, sans-serif`; and
  `"Anthropic Mono", "JetBrains Mono", "SF Mono", Menlo, monospace`.
- A main headline may contain one italic clay word when that word carries the
  decisive conclusion. Do not scatter clay emphasis across the slide.
- Kickers are small, uppercase Anthropic Sans in clay, with restrained wide tracking.
- No center-content text may be smaller than **16 px** at the normal 16:9 browser
  viewport. Editorial body copy should normally be 21–22 px at 1.35–1.4
  line-height, subheadings 26 px, declarative sans headings about 64–68 px, serif
  display headings about 68–72 px, chart labels at least 16 px after scaling, and result numbers
  substantially larger.
- Use subtle negative tracking only for compact sans text: approximately `-0.005em`
  at 15–16 px and `-0.002em` at display sizes. Serif text keeps normal tracking.
- Use tabular figures for quantitative values where available.
- Keep body copy short enough to read comfortably from the back of a room.

Load Source Serif 4 and Inter when the output format supports web fonts. Always
declare the Anthropic family names first so licensed/local versions are used when
available, followed by the portable substitutes above for reproducible rendering.

### Type scale

| Role | Family | Size | Line height | Weight |
| --- | --- | --- | --- | --- |
| Caption or footnote | Anthropic Serif or Sans | 16 px | 1.35–1.4 | 400–600 |
| Compact body | Anthropic Serif | 18–20 px | 1.35–1.4 | 400 |
| Body | Anthropic Serif | 21–22 px | 1.35–1.4 | 400 |
| Subheading | Anthropic Serif or Sans | 26 px | 1.25–1.3 | 400–600 |
| Declarative heading | Anthropic Sans | 64–68 px | 1.03–1.08 | 700 |
| Editorial display | Anthropic Serif | 68–72 px | 1.03–1.08 | 400–600 |

### Project arch adaptation

The arch is a secondary project signature, not the default container. It has a
fully rounded top and square bottom. Use it sparingly for:

- photographs or simple illustration areas;
- portrait frames;
- number tokens;
- vertical bars, whose tops should read like arch windows.

If an arch is used, a thin clay outline may sit 4–6 pixels behind it as an echo.
Never add a shadow.

Do not place dense data plots, heatmaps, or figures with embedded text inside an arch
or window-like frame. Present those figures without decorative borders and make them
large enough that their internal labels remain legible.

Do not place recurring decorative arches in a corner. Every visible arch must carry
a framing or quantitative function. If it does not convey information or organize
the composition, remove it.

### Surfaces, lines, and composition

- Canvas is Ivory Medium. Standard cards are Ivory Light; grouped panels may use Oat
  Warm; one editorial feature may use Manilla. Slate Dark is the only full dark
  inversion.
- Elevation comes from surface-tone shifts and one-pixel Stone borders, never from
  shadows.
- Default card radius is 24 px. Badges and inline labels are unboxed with zero
  radius. Do not use generic pill containers.
- Rules are one-pixel Stone lines.
- Compositions are asymmetric but visually balanced.
- Use the canvas efficiently. Default slide padding should be approximately
  `18–24px 2vw`, with central content allowed to occupy about 96% of the slide
  width. Relative to the original 1440 px content canvas, standard slides should
  target approximately 1720 px at 1920×1080—about 20% more central area. Do not
  surround a small center block with a large unused perimeter.
- Enlarge the entire hierarchy together: typography, charts, cards, controls, and
  spacing between related elements. A larger headline beside unchanged tiny body
  copy does not satisfy the scale target.
- Preserve deliberate whitespace *between* content groups, but do not confuse
  oversized outer margins with clarity.
- Let the primary figure or result use up to roughly 68–74% of slide height when it
  remains legible.
- Prefer one dominant idea, result, or graphic per slide.
- Cards may have quiet 24 px corners; filled action-like tabs use square top corners
  with an 8 px bottom-only radius.
- Avoid dense card grids, excessive borders, and dashboard-like layouts.
- Do not add decorative hero imagery by default. If a scientific illustration is
  useful, prefer a warm naturalist field-guide style over photography, product
  screenshots, or abstract gradients.

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
- The current slide is larger and Slate Dark; inactive slides use Cloud Dark or
  Stone.
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
- Use neutral gray for a baseline. In ranked bar charts, use Muted Blue to highlight
  the numerical winner, Sage for a secondary specialist or automatic method, and
  Soft Sage for a blend when those distinctions are scientifically meaningful. Do
  not assign the strongest accent merely by series order. Use Clay/Clay Deep for
  interference, warning, or the single comparison that requires attention.
- Encode meaning with a semantic class such as `.winner`; do not hard-code “the
  second bar is blue.” If the result changes, the highlight must follow the verified
  winner.
- Use Oat Warm, Ivory Light, and Stone for tracks, reference bands, and neutral
  areas.
- Use Slate Dark for axes and labels; keep Stone grid lines sparse and low-opacity.
- Bars may have rounded tops when the arch carries quantitative meaning; otherwise
  use quiet 8–24 px radii.
- Label important values directly when possible.
- When importing a raster chart, allocate enough slide width for its embedded labels
  to remain readable; do not shrink a chart merely to preserve a large text column.
- Prefer a chart-dominant split of roughly 70–76% visual width on result slides,
  and allow those slides to use a wider content canvas than text-led slides.
- Remove decorative frames, rounded windows, and outline echoes from dense plots.
- Do not rely on color alone: retain signs, values, intervals, or concise labels.
- Preserve scientific uncertainty and claim boundaries; visual polish must not
  promote exploratory results into confirmed findings.

### Canonical web tokens

```css
:root {
  --slate-dark: #141413;
  --ivory-medium: #f0eee6;
  --ivory-light: #faf9f5;
  --cloud-medium: #b0aea5;
  --cloud-dark: #87867f;
  --stone: #cccbc8;
  --slate-medium: #3d3d3a;
  --oat-warm: #e3dacc;
  --manilla: #f5e3c7;
  --clay: #d97757;
  --clay-deep: #c6613f;
  --sage: #7A8C6F;
  --sage-soft: #91A087;
  --muted-blue: #798C91;
  --sage-deep: #62785B;

  --font-anthropic-serif:
    "Anthropic Serif", "Source Serif 4", Georgia, Charter, serif;
  --font-anthropic-sans:
    "Anthropic Sans", Inter, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", Arial, sans-serif;
  --font-anthropic-mono:
    "Anthropic Mono", "JetBrains Mono", "SF Mono", Menlo, monospace;

  --text-caption: 16px;
  --text-body-sm: 16px;
  --text-body: 22px;
  --text-subheading: 26px;
  --text-heading: 68px;
  --text-display: 72px;

  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --space-8: 32px;
  --radius-card: 24px;
}
```

These tokens describe the presentation implementation, not a web-product UI. Omit
site-only components such as cookie banners, global navigation, or marketing CTAs
unless the presentation itself genuinely requires an analogous function.

### Current 1920×1080 reference implementation

Use these values as the starting point for future 16:9 decks. Reflow content before
reducing them:

| Element | Reference value |
| --- | --- |
| Slide padding | `22px 2vw` |
| Standard content canvas | `1720px` maximum |
| Chart-dominant result canvas | `1760px` maximum |
| Editorial display / `h1` | `70px`, line-height `1.03` |
| Result headline / `h2` | `50px`, line-height `1.06` |
| Card heading / `h3` | `26px` |
| Body copy | `22px` |
| Compact panel copy | `20px` |
| Kicker and compact labels | `16px` minimum |
| Retained footnotes and captions | `17px` by default; never below `16px` |
| Card padding | approximately `26px 28px` |
| Result-column gap | approximately `32px` |
| Standard/result canvas increase | `1440→1720px`; result slides may reach `1760px` |

Keep centered pagination dots, the explicit 180 ms transition, reduced-motion
support, frameless plot integration, and the semantic `.winner` data highlight as
part of the same reference implementation.

### Footnote policy

- Do not use tiny-print footnotes. Any caveat, cohort label, metric definition, or
  evidence boundary important enough to keep must render at **16 px or larger** at
  1920×1080.
- Rewrite important notes into one short sentence and give them a reserved footer
  lane or a clearly associated caption.
- If a note is redundant, operational trivia, or unnecessary for interpreting the
  slide, remove it instead of shrinking it.
- Footer notes must not collide with centered pagination or sit against the viewport
  edge. Chart captions follow the same 16 px minimum when they carry interpretive
  meaning.

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

### Required closing future-work slide

End a research-progress deck with a dedicated **next step / future work** slide
rather than burying the plan in a small callout on the last result slide.

- State the immediate experiment in one plain-language sentence.
- Show two or three prespecified decision branches based on possible outcomes.
- Separate the next experiment from longer-term ambitions.
- End with the intended scientific or practical deliverable.
- Do not imply that every branch will be pursued; make the decision gate explicit.
- If a new result arrives before the talk, insert a bounded result slide before this
  closer and update the applicable branch. Do not replace the closing decision slide
  with runtime progress or an ETA.
- Use equally weighted flat cards with restrained semantic top rules. No branch
  receives “winner” styling before its criterion is met.

## No talking scripts

Do not create presenter scripts, timed narration, or slide-by-slide prose intended to
be read aloud. The maintained presentation package consists of:

- the rendered deck;
- the visual assets loaded by that deck;
- this canonical design specification; and
- canonical scientific result/protocol documents outside the presentation folder.

The slides must be understandable without a script. Delete obsolete script files
rather than carrying them forward. Do not create a parallel content brief or
readiness checklist after the deck is self-contained. Put evidence verification and
detailed technical context in canonical scientific documentation, tests, and frozen
artifacts—not in presentation-only companion documents.

## Non-regression lessons from visual QA

These are universal requirements derived from the July 30 deck review:

- Measure typography in the **rendered 16:9 slide**, not only in the source CSS or
  chart-generation code. The 16 px floor applies to visible center content after
  layout; embedded raster labels must also be readable at the final displayed size.
- Dense scientific figures receive priority over a wide prose column. Shorten or
  reflow the explanation before shrinking a heatmap or chart below legibility.
- Imported plots must visually belong to the cream slide. Remove window-like
  borders and rounded frames, and use a transparent plot background or verified
  blend treatment so a white rectangular canvas does not reappear. Avoid an
  unnecessary ancestor stacking context that prevents `mix-blend-mode` from
  integrating the figure background.
- Reserve a clear footer lane. Captions, caveats, and callouts must not clip at the
  viewport edge or collide with the centered progress dots.
- Navigation is part of the template: centered dots, a visibly darker/larger active
  dot, keyboard support, direct-dot navigation, and the explicit 180 ms transition
  must remain together.
- Static markup checks are not enough. Render every dense result slide at
  **1920×1080**, inspect it visually, and confirm text fit, chart-label legibility,
  active pagination, background integration, and absence of clipping. Repeat the
  check in the exported delivery format.

## Slide-level checklist

For every slide:

1. Use the Ivory Medium canvas and Anthropic serif/sans type system.
2. Use at most one italic Clay headline word, and only when it carries the decisive
   conclusion.
3. Use at most one primary visual hierarchy.
4. Use the arch motif only when it has a framing, navigational, or quantitative
   function.
5. Fill the central canvas without oversized perimeter whitespace; retain breathing
   room between content groups.
6. Verify that no pure white, pure black, neon, gradients, shadows, saturated
   decoration, or unnecessary sharp-cornered imagery remains.
7. Verify the 180 ms transition and reduced-motion behavior.
8. For biweekly decks, verify that results occupy most of the presentation and that
   failure chronology is not part of the main narrative.
9. Verify that a nontechnical audience can understand every headline, metric, and
   comparison without project-specific background.
10. Confirm that center-content text is at least 16 px and imported-chart labels
    remain readable at presentation scale.
11. Verify centered pagination dots and the active-slide state.
12. Ask whether a visual would communicate the slide more clearly than prose.
13. Confirm that no talking script or timed narration file was created.
14. Check legibility at 16:9 presentation scale and in exported print/PDF output.
15. Confirm imported plots blend into the cream canvas without a white rectangle or
    decorative window frame.
16. Confirm captions, caveats, and callouts do not collide with the pagination lane
    or clip at any viewport edge.
17. Keep every retained footnote at 16 px or larger; delete any note that does not
    materially affect interpretation.

## Scientific presentation safeguard

Theme changes may alter layout and visual treatment, but must not change numerical
results, evidence labels, uncertainty, cohort definitions, protocol hashes, or claim
boundaries. Any substantive content update belongs in the dated presentation brief
before it is rendered into slides.
