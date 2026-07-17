# KAFKA Evidence UI

Evidence-first design system derived from the KAFKA2306 portfolio.

- Repository inventory snapshot: **165 owned repositories on 2026-07-17**
- Implementation review: representative projects across finance, public-data BI, catalogs, VR, browser extensions, and personal sites
- Delivery: plain HTML/CSS/JavaScript showcase plus reusable Claude Code, Codex, and `agr` skills

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
├── components.css
├── audit-report.md
├── audit-scope.md
└── decision-log.md
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

```text
codex plugin marketplace add KAFKA2306/agent-resources
```

Codex can also discover the repository skill at `.agents/skills/kafka-evidence-ui/SKILL.md`.

## agr-compatible agents

```bash
agr add KAFKA2306/agent-resources/kafka-evidence-ui
```

## Evidence boundary

The complete repository inventory was enumerated. Implementation-level findings are based on the representative projects listed in [audit-report.md](audit-report.md); the report does not claim that every visual file in all 165 repositories was rendered and inspected.
