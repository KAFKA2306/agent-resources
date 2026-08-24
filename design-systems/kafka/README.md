# KAFKA Evidence UI

Evidence-first design system for dense operational interfaces.

- Delivery: plain HTML/CSS/JavaScript showcase plus reusable Claude Code, Codex, and `agr` skills
- Canonical rules live in the current tokens, components, showcase, and reusable skill assets

## Design thesis

> Evidence, state, and uncertainty remain visible while the interface stays dense enough for real analysis.

The system has two modes with one shared grammar:

- **terminal** — monitoring, finance, operations, logs, and audit-heavy interfaces;
- **paper** — public-data BI, catalogs, reports, libraries, and explanatory interfaces.

## Files

```text
design-systems/kafka/
├── index.html
├── app.js
├── tokens.css
└── components.css
```

The reusable plugin is under `plugins/kafka-evidence-ui/`.

## Run locally

No build step is required.

```bash
python -m http.server 8000
```

Open `/design-systems/kafka/`.

## Claude Code

```text
/plugin marketplace add KAFKA2306/agent-resources
/plugin install kafka-evidence-ui@kafka-agent-tools
```

## Codex

Use the Codex / ChatGPT Plugin Directory for plugin installation on supported surfaces.

Codex can also discover the repository skill directly at `.agents/skills/kafka-evidence-ui/SKILL.md`.

## agr-compatible agents

```bash
agr add KAFKA2306/agent-resources/kafka-evidence-ui
```
