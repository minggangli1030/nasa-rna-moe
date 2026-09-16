# September 14 — space-biology discovery

- [Three-slide HTML deck](2026-09-14-discovery.html)
- [Three-page widescreen PDF](2026-09-14-discovery.pdf)
- [Short speaking script, approximately 3 minutes](2026-09-14-speaking-script.md)

Open the HTML in a browser. Use **← / →**, **Page Up / Down**, **Space**, or the centered dots to navigate. Press **N** for the current slide's speaking script and **Esc** to close it. The charts are embedded as vectors; internet access is optional for web fonts and local font fallbacks are provided.

The deck reuses the layout, color and typography tokens, pagination and 180 ms navigation from [the August 17 template](../../su26/presentation/2026-08-17-final.html), following the [shared visual specification](../../su26/presentation/design.md). The speaking script is included as requested for this update.

Evidence comes from the [completed pathway/onboard-1g report](../artifacts/pathway_onboard_1g_2026-09-13/REPORT.md). The two charts are generated from its saved results; exact plotted values are saved in `2026-09-14-chart-values.json`. The main deck shows selected leads; the canonical report retains the full ten-set panel and failed comparisons.

Rebuild with `python3 fa26/presentation/build_september14.py`. Export and check with `python3 fa26/presentation/export_september14.py` (Python Playwright and installed Chrome). All three slides were rendered and visually inspected at 1920×1080 and 1280×720, and in the three-page PDF. Navigation, notes and content fit were checked.
