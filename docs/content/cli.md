---
title: AGR CLI
---

# AGR CLI — Skills for AI Agents

AGR は AI agent skills を導入・共有・実行するCLIです。Software Factory Control Towerとは別の役割ですが、同じrepositoryで配布しています。

## Install

~~~bash
uv tool install git+https://github.com/KAFKA2306/agent-resources.git
~~~

## Common workflows

### Install a skill

~~~bash
agr add anthropics/skills/frontend-design
~~~

### Run a skill once

~~~bash
agrx anthropics/skills/pdf
agrx anthropics/skills/pdf -p "Extract tables from report.pdf"
agrx anthropics/skills/pdf -i
~~~

### Sync team dependencies

~~~toml
dependencies = [
    {handle = "anthropics/skills/frontend-design", type = "skill"},
    {handle = "anthropics/skills/skill-creator", type = "skill"},
]
~~~

~~~bash
agr sync
~~~

### Create a skill

~~~bash
agr init my-skill
~~~

## Quick reference

| Command | Purpose |
|---|---|
| `agr add <handle>` | install a skill |
| `agr remove <handle>` | uninstall a skill |
| `agr sync` | install dependencies from `agr.toml` |
| `agr list` | show installation status |
| `agr init` | create `agr.toml` |
| `agr init <name>` | create a skill scaffold |
| `agr onboard` | guided setup |
| `agrx <handle>` | run a skill temporarily |

## Handle format

~~~bash
agr add user/skill
agr add user/repo/skill
agr add ./path/to/skill
~~~

AGR searches the common skill locations in the selected repository and rejects ambiguous duplicate names instead of guessing.

## Next

- [Creating Skills](creating.md)
- [Full CLI Reference](reference.md)
