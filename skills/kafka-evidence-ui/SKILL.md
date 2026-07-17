---
name: kafka-evidence-ui
description: Design or refactor information-dense HTML, CSS, JavaScript, and frontend interfaces in KAFKA2306's evidence-first visual system. Use for dashboards, catalogs, monitoring tools, public-data BI, finance or VR utilities, and design-system migrations. Do not use for backend-only tasks or when another brand system is explicitly required.
---

# KAFKA Evidence UI

Build interfaces that make evidence, state, and uncertainty easier to inspect than decoration.

## Start with the existing product

1. Read the current HTML, CSS, JavaScript, components, and data model before editing.
2. Preserve working behavior, terminology, routes, and data contracts unless the task explicitly changes them.
3. Identify the user's primary decision: inspect, compare, monitor, search, operate, or verify.
4. Inventory the evidence the interface can expose: source, timestamp, sample count, coverage, missing fields, blocked claims, and unresolved records.

## Choose one mode

- **Terminal mode**: monitoring, finance, operational control, logs, audit matrices, and high-frequency comparison.
- **Paper mode**: public-data BI, catalogs, reports, libraries, explanatory tools, and source-led browsing.

Use the same spacing, typography, component, and semantic-state rules in both modes. Do not invent a third visual language for each project.

## Use the supplied assets

- `assets/tokens.css`: semantic colors, type, spacing, radius, density, and terminal/paper themes.
- `assets/components.css`: shell, navigation, metrics, panels, controls, tables, bars, evidence records, badges, and responsive behavior.

Copy or import these files. Override semantic tokens rather than scattering literal colors through project CSS.

## Required information architecture

Place these in a stable reading order when the data exists:

1. identity and current scope;
2. freshness and system/data status;
3. primary metrics or selected object;
4. controls and filters;
5. detailed table, catalog, chart, or workflow;
6. evidence lane with source, coverage, assumptions, and unresolved items.

Missing or blocked evidence must remain visible. Never convert an unknown value into a confident claim.

## Visual constraints

- Base spacing on 4px increments; use 8px as the default gap.
- Default radius is 8px. Use only 0, 4px, 8px, or pill radius.
- Use one focus accent. Reserve positive, warning, negative, information, and special colors for semantic states.
- Use sans-serif for prose and controls; use monospace for numbers, identifiers, timestamps, paths, statuses, and compact labels.
- Prefer thin borders and surface contrast. Do not put a shadow on every card.
- Use shadows only for overlays, popovers, or a genuinely floating control.
- Keep controls compact and sticky only when they remain useful during scrolling.
- Tables use sticky headers, aligned numeric columns, clear hover/focus states, and horizontal overflow on small screens.

## Prohibited defaults

Do not introduce these without a specific product reason:

- rainbow accent palettes;
- gradient-filled headings;
- pervasive glass blur;
- glowing panels;
- hover lift on every card;
- 18–24px default corner radii;
- oversized empty hero areas;
- decorative icons without labels or operational meaning;
- hidden source, freshness, coverage, or uncertainty information.

## HTML, CSS, and JavaScript rules

- Prefer semantic HTML and native controls.
- Make interactive elements keyboard reachable and provide visible `:focus-visible` states.
- Use `aria-pressed`, `aria-live`, labels, and status roles where state changes need to be announced.
- Keep JavaScript progressive and local: theme, density, filtering, sorting, copy, disclosure, and synchronized selection.
- Persist only harmless presentation preferences in `localStorage`.
- Respect `prefers-reduced-motion`.
- Do not add a framework when plain HTML, CSS, and JavaScript satisfy the task.
- Do not remove an established framework solely to satisfy this skill.

## Validation checklist

Before finishing, verify:

- the primary decision is visible without scrolling on a common laptop viewport;
- source and freshness are present where available;
- missing, warning, failed, stale, and blocked states are distinguishable without relying only on color;
- contrast, keyboard navigation, responsive layout, and reduced motion work;
- literals have been consolidated into semantic tokens;
- the interface has no unnecessary gradient, glow, blur, lift, shadow, or oversized radius;
- the implementation still passes its existing build, lint, and test commands.

Report the selected mode, evidence exposed, files changed, validations run, and any remaining proof gaps.
