---
title: Home
---

# AGR CLI — Skills for AI Agents

AGR は、この公開Agent運用ハブでAI agent skillsを導入・共有・実行するためのCLIです。repository全体の運用状況は https://agent-resources-one.vercel.app/ で確認できます。

## Install

```bash
uv tool install git+https://github.com/KAFKA2306/agent-resources.git
```

## Choose Your Path

### Install a Skill (persist it)

```bash
agr add anthropics/skills/frontend-design
```

This installs the skill into your tool's skills folder. Use `--source <name>` to
pick a non-default source from `agr.toml`.

### Run a Skill Once (no install)

```bash
agrx anthropics/skills/pdf                  # Run once, then clean up
agrx anthropics/skills/pdf -p "Extract tables from report.pdf"
agrx anthropics/skills/pdf -i               # Interactive: run skill, then continue chatting
```

The `-i` flag runs the skill first, then starts an interactive session so you can
continue the conversation.

### Share with Your Team

Dependencies are tracked in `agr.toml`:

```toml
dependencies = [
    {handle = "anthropics/skills/frontend-design", type = "skill"},
    {handle = "anthropics/skills/skill-creator", type = "skill"},
]
```

Teammates install everything with:

```bash
agr sync
```

### Create a Skill

```bash
agr init my-skill
```

Then edit `my-skill/SKILL.md`. If you want it in this repo, place it under
`./skills/`.

## Commands (Quick Reference)

| Command | What it does |
|---------|-------------|
| `agr add <handle>` | Install a skill |
| `agr remove <handle>` | Uninstall a skill |
| `agr sync` | Install all dependencies from `agr.toml` |
| `agr list` | Show skills and installation status |
| `agr init` | Create `agr.toml` (auto-detects tools) |
| `agr init <name>` | Create a skill scaffold |
| `agr onboard` | Interactive guided setup |
| `agrx <handle>` | Run a skill temporarily |

## Handle Format

```bash
agr add user/skill              # From user's "skills" repo
agr add user/repo/skill         # From a different repo
agr add ./path/to/skill         # Local path
```

## How Skill Discovery Works

When you run `agr add user/repo/skill`, agr searches that repo for a skill named
`skill`. It will be found if it exists in:

- `resources/skills/{skill}/SKILL.md`
- `skills/{skill}/SKILL.md`
- `{skill}/SKILL.md`

If two skills have the same name, you'll get an error.

## Project Setup

```bash
agr init       # Create agr.toml (auto-detects tools)
agr onboard    # Interactive guided setup
```

`agr init` creates `agr.toml` and detects which tools you use from repo signals
(`.claude/`, `CLAUDE.md`, `.cursor/`, `.cursorrules`, etc.).

`agr onboard` walks you through tool selection, skill discovery, migration from
tool folders into `./skills/`, and configuration.

## Example Skills

```bash
agr add anthropics/skills/frontend-design    # Build production-grade UIs
agr add anthropics/skills/skill-creator      # Create new skills
agr add anthropics/skills/pdf                # Work with PDF documents
```

Browse more at [github.com/anthropics/skills](https://github.com/anthropics/skills).

## Next Steps

- [Create your own skill](creating.md)
- [CLI reference](reference.md)
