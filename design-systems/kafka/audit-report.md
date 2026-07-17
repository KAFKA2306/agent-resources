# KAFKA Evidence UI — Portfolio Audit

**Snapshot:** 2026-07-17  
**Repository inventory:** 165 repositories owned by `KAFKA2306`  
**Implementation review:** representative, cross-domain review; not every file in every repository

## Method

The audit used two layers:

1. enumerate the complete owned-repository inventory and classify likely delivery surfaces;
2. inspect implementation files from representative web, dashboard, catalog, extension, finance, public-data, VR, and personal-site projects.

A design rule is accepted only when supported by repeated implementation evidence, an explicit owner preference, or a deliberate corrective decision. Repository names alone are not treated as visual evidence.

## Representative implementation review

| Project | Surface inspected | Accepted evidence | Corrective finding |
|---|---|---|---|
| [PAL ATLAS](https://github.com/KAFKA2306/pal-atlas) | Vite, plain JavaScript, CSS tokens, catalog/detail UI | dual dark/light themes, dense cards, thin borders, monospace metadata, source and rank visibility | reduce simultaneous accents and strong panel shadows |
| [US Swing Strategy BI Pages](https://github.com/KAFKA2306/us-swing-strategy-bi-pages) | static Astro output, audit terminal CSS | visible audit gaps, source-file lane, timestamps, counts, compact tables, 8px rhythm | preserve density while avoiding ornamental terminal imitation |
| [Game Library Dashboard](https://github.com/KAFKA2306/game-library-dashboard) | static HTML/CSS/JS dashboard | warm paper palette, ontology, sticky filters, mono metrics, evidence section | reduce card shadow where borders already establish hierarchy |
| [Cedar Pollen BI](https://github.com/KAFKA2306/cedar-pollen-bi) | public-data BI, map, table, official-source navigation | source-led information architecture, interpretation boundaries, compact charts and tables | keep one focus accent and reduce repeated floating-panel treatment |
| [TraHist](https://github.com/KAFKA2306/trahist) | server-rendered dashboard template | dark operational surface, stats, tabs, tables, mono amounts | generic slate palette, gradient heading, large radius and padding |
| [ボドゲのミカタ](https://github.com/KAFKA2306/bodogenomikata2) | React/Vite frontend and CSS | searchable dense catalog, useful metadata, responsive card system | excessive glow, blur, radial gradients, hover lift, and 18–24px radii |
| [ReadableGitHub](https://github.com/KAFKA2306/readable-github) | browser-extension injected UI and popup | compact controls, restrained 4–6px radii, direct status colors | consolidate literal colors into semantic tokens |
| [VRChat Gallery](https://github.com/KAFKA2306/vrcviewer) | large static gallery | straightforward search/filter/card hierarchy | generic white cards, large gaps, shadow and universal hover lift are migration targets |
| [aboutkafka](https://github.com/KAFKA2306/aboutkafka) | React/Tailwind personal site | expressive historical profile surface | full-page rainbow gradient and repeated translucent sections are an outlier, not the current core |
| [2510youtuber GUI design](https://github.com/KAFKA2306/2510youtuber/blob/main/docs/GUI_DESIGN.md) | architecture and UI specification | loose coupling, minimum viable surface, observability, configuration-driven commands, logs, artifacts, diagnostics | convert these principles into reusable visual and interaction rules |

## Core design thesis

KAFKA2306's durable interface identity is not a decorative motif. It is an operating model:

> Evidence, state, and uncertainty remain visible while the interface stays dense enough for real analysis.

The system therefore uses two modes that share one grammar.

### Terminal mode

Use for finance, monitoring, operational control, logs, audit matrices, execution state, and high-frequency comparison.

- near-black background and layered dark surfaces;
- compact controls and tables;
- monospace statuses, timestamps, numbers, identifiers, and paths;
- explicit positive, warning, negative, information, and special states;
- minimal radius and no default panel shadow.

### Paper mode

Use for public-data BI, catalogs, libraries, reports, explanatory tools, and source-led browsing.

- warm ivory background rather than sterile white;
- ink, steel-blue focus, and restrained semantic colors;
- the same density, border, spacing, and evidence rules as terminal mode;
- tables, filters, metrics, and source records remain operational rather than editorial decoration.

## Accepted rules

1. **Evidence first.** Expose source, freshness, counts, coverage, assumptions, missing fields, and blocked claims when available.
2. **Dense by default.** Use a 4px base and 8px default gap. Comfortable density is an explicit user choice.
3. **Quiet hierarchy.** Prefer surface contrast and thin borders over shadows, blur, and glow.
4. **One focus accent.** Semantic status colors do not become decorative palette colors.
5. **Monospace evidence.** Numbers, identifiers, timestamps, paths, compact labels, and statuses use monospace.
6. **Stable reading order.** Identity → current state → metrics → controls → detail → evidence lane.
7. **Visible uncertainty.** Missing, stale, failed, blocked, and special-case states include text, not color alone.
8. **Operational responsiveness.** Controls remain usable, tables overflow safely, and the primary decision is visible on a common laptop viewport.

## Corrective constraints

The following are denied by default because they recur as noise or inconsistency across older and highly styled projects:

- rainbow accent palettes;
- gradient-filled headings;
- pervasive glass blur;
- glowing panels;
- hover lift on every card;
- 18–24px default corner radii;
- a shadow on every surface;
- oversized empty hero regions;
- hidden evidence, freshness, coverage, or uncertainty;
- decorative icons without labels or operational meaning.

Allowed radii are `0`, `4px`, `8px`, and pill. Shadows are reserved for overlays, popovers, or genuinely floating controls.

## Migration priority

1. New dashboards and tools use the system directly.
2. Current high-value interfaces consolidate literal colors and component rules without rewriting their frameworks.
3. Older generic galleries and personal pages migrate only when they are actively maintained.
4. Project-specific imagery and domain colors may remain, but they must not replace semantic state tokens.

## Evidence boundary

The complete inventory count is verified for the snapshot date. The implementation findings are based on the representative projects listed above. The audit does **not** claim that every visual file in all 165 repositories was rendered and inspected.
