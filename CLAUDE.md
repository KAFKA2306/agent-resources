# Claude Code

このrepositoryの共通運用ルールは [AGENTS.md](AGENTS.md) を正準とします。

Claude固有の差分が必要になった場合だけ、このファイルへ追加してください。共通のcommands、architecture、GitHub write手順、security、documentation方針をここへ複製しません。

長時間・background session、context statusline、hooksによるobservability、Claude設定JSONのdiffを扱う場合は [skills/claude-code-operations/SKILL.md](skills/claude-code-operations/SKILL.md) を使います。Claude Code標準機能を優先し、独自daemonや並行status authorityを追加しません。
