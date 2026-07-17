# KAFKA Evidence UI

Evidence-first design system and agent skill for KAFKA2306 projects.

## Modes

- `terminal`: monitoring, finance, operations, logs, and audit-heavy tools.
- `paper`: public-data BI, catalogs, reports, libraries, and explanatory tools.

Both modes share the same semantic tokens, spacing, density, components, and evidence rules.

## Contents

```text
.claude-plugin/plugin.json
.codex-plugin/plugin.json
skills/kafka-evidence-ui/SKILL.md
assets/tokens.css
assets/components.css
```

## Claude Code

```text
/plugin marketplace add KAFKA2306/agent-resources
/plugin install kafka-evidence-ui@kafka-agent-tools
```

## Codex

```text
codex plugin marketplace add KAFKA2306/agent-resources
```

The plugin can also be discovered directly as a repository skill under `.agents/skills/kafka-evidence-ui`.

## agr-compatible installation

```bash
agr add KAFKA2306/agent-resources/kafka-evidence-ui
```

## Plain HTML/CSS/JS

Copy `assets/tokens.css` and `assets/components.css`, then set the theme on the root element:

```html
<html data-theme="terminal" data-density="compact">
```

Use `data-theme="paper"` for the warm light mode.

## Design rule

Evidence, freshness, coverage, state, and uncertainty remain visible. Decorative effects never outrank the user's primary decision.
