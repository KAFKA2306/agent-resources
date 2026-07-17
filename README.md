<div align="center">

# 🧩 agent-resources (agr)

**A package manager for AI agents.**

Install agent skills from GitHub with one command.

[![PyPI](https://img.shields.io/pypi/v/agr?color=blue)](https://pypi.org/project/agr/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

---

## Getting Started

Install agr CLI:

```bash
pip install agr
```

Install your first skill:

```bash
agr add anthropics/skills/frontend-design
```

That's it. The skill is now available in your configured tool (Claude Code, Codex, Cursor, OpenCode, Copilot, or Antigravity).

---

## What is agr?

**agr** installs agent skills from GitHub directly into your tool's skills folder
(`.claude/skills/`, `.codex/skills/`, `.cursor/skills/`, `.opencode/skill/`, `.github/skills/`, or `.agent/skills/`).

**agrx** runs skills instantly from your terminal — download, run, then clean up.

---

## Install Skills

```bash
agr add anthropics/skills/frontend-design     # Install a skill
agr add -g anthropics/skills/frontend-design  # Install globally for your user
agr add anthropics/skills/pdf anthropics/skills/mcp-builder   # Install multiple
agr add anthropics/skills/pdf --source github # Install from an explicit source
```

Remote installs require `git` to be available on your system.

### Handle format

```
username/skill-name         → From user's skills repo
username/repo/skill-name    → From a specific repo
./path/to/skill             → From local directory
```

Note: `username/skill-name` now defaults to a repo named `skills`. During a
deprecation period, agr will fall back to `agent-resources` (with a warning) if
the skill isn't found in `skills`.

---

## Run Skills From Your Terminal

```bash
agrx anthropics/skills/pdf                              # Run a skill instantly
agrx anthropics/skills/pdf -p "Extract tables from report.pdf"   # With a prompt
agrx anthropics/skills/skill-creator -i                 # Run, then continue chatting
agrx anthropics/skills/pdf --tool cursor                # Use a specific tool
```

---

## Team Sync

Your dependencies are tracked in `agr.toml`:

```toml
dependencies = [
    {handle = "anthropics/skills/frontend-design", type = "skill"},
    {handle = "anthropics/skills/brand-guidelines", type = "skill"},
]
```

Teammates run:

```bash
agr sync
```

---

## Create Your Own Skill

```bash
agr init my-skill
```

Creates `my-skill/SKILL.md`:

```markdown
---
name: my-skill
description: What this skill does.
---

# My Skill

Instructions for the agent.
```

If you're adding it to this repo, place it under `./skills/`.

Test it locally:

```bash
agr add ./skills/my-skill
```

Share it:

```bash
# Push to GitHub, then others can:
agr add your-username/my-skill
```

---

## Initialize a Repo

```bash
agr init       # Create agr.toml (auto-detects tools)
agr onboard    # Interactive guided setup
```

`agr init` creates `agr.toml` and detects which tools you use from repo signals (`.claude/`, `CLAUDE.md`, `.cursor/`, etc.).

`agr onboard` walks you through tool selection, skill discovery, migration, and configuration interactively.

---

## All Commands

| Command | Description |
|---------|-------------|
| `agr add <handle>` | Install a skill |
| `agr add -g <handle>` | Install a skill globally |
| `agr remove <handle>` | Uninstall a skill |
| `agr remove -g <handle>` | Uninstall a global skill |
| `agr sync` | Install all from agr.toml |
| `agr sync -g` | Sync global dependencies |
| `agr list` | Show installed skills |
| `agr list -g` | Show global skills |
| `agr init` | Create agr.toml |
| `agr init <name>` | Create a new skill |
| `agr onboard` | Interactive guided setup |
| `agr config <cmd> <key>` | Manage agr.toml (show, get, set, add, remove, unset, edit, path) |
| `agrx <handle>` | Run skill temporarily |

---

## Community Skills

```bash
# Go development — @dsjacobsen
agr add dsjacobsen/golang-pro

# Drupal development — @madsnorgaard
agr add madsnorgaard/drupal-expert
```

**Built something?** [Share it here](https://github.com/kasperjunge/agent-resources/issues).

## KAFKA Evidence UI

Evidence-first design system for dense dashboards, catalogs, monitoring tools, and public-data interfaces.

- [GitHub Pages showcase](https://kafka2306.github.io/agent-resources/)
- [Design system skill](skills/kafka-evidence-ui/SKILL.md)
- [Agent plugin](plugins/kafka-evidence-ui/README.md)

---

## Coming from npx skills?

agr uses a slightly different handle format than `npx skills`:

| What you want | npx skills | agr |
|---|---|---|
| Skill from a repo | `npx skills add owner/repo` | `agr add owner/repo/skill-name` |
| Skill from user's default repo | — | `agr add owner/skill-name` |

The key difference: `agr` handles always point to a **specific skill**, not a
repo to scan. Use the three-part format `owner/repo/skill-name` when the skill
lives in a non-default repo.

If you use a two-part handle and the skill isn't found, `agr` will check if a
matching repository exists and suggest the correct handles.

---

<div align="center">

[Documentation](https://kafka2306.github.io/agent-resources/) · [MIT License](LICENSE)

</div>
