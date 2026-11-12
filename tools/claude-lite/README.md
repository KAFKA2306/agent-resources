# Claude Code lite evaluation runner (optional)

A reusable, small runner for KAFKA2306 projects. It is an experimental implementation of the ISUCON2026 bare/lite lessons, not a replacement for project-owned AGENTS.md or a new factory authority.

## Run on Linux / WSL2 (GNU date)

Authenticate the dedicated config once:
~~~bash
CLAUDE_CONFIG_DIR="$HOME/.agent-eval/claude-config" claude auth login
~~~

Copy CONDITIONS.example.md elsewhere and fill in the real task, scoring and permitted deployment boundaries. Then:
~~~bash
bash tools/claude-lite/run.sh https://github.com/KAFKA2306/LLM_trader.git /absolute/path/CONDITIONS.md 2026-11-13T04:00:00+09:00
~~~
The last deadline argument is optional. Each execution clones to ~/.agent-eval/runs/lite-*/source and runs Claude from the parent isolated directory. It does not modify the original checkout. The inherited environment is cleared, and the dedicated Claude config is reused for authentication. Project and local settings come from the isolated root, not from source/. Inherited user settings and MCP servers are disabled. MCP tools are denied again via settings. This uses dontAsk, not bypassPermissions.

## Guard and hooks

From the run directory:
~~~bash
make -f Makefile.guard check-clean
make -f Makefile.guard bench BENCH_CMD='real benchmark command'
make -f Makefile.guard record-score SCORE=123
make -f Makefile.guard deploy DEPLOY_CMD='authorized deploy command'
~~~
Deploy and bench refuse a dirty source/ checkout; real command values are intentionally not prefilled. The record-score command is only for *verified* benchmark output. PostToolUse adds context after 30 minutes without a new recorded best score and during the last 40 minutes before a provided deadline. SessionStart(compact) restores conditions. No score means no stagnation signal. These hooks do not themselves run benchmarks or launch subagents.

## Safety and evaluation limits

Claude Code permission rules are **not an OS sandbox**. Arbitrary subprocesses can bypass file-tool deny rules. Managed policy can still apply. For untrusted code, use a container/VM, separate OS identity, restricted filesystem/network and spending limits. The Makefile gate only protects commands routed through it; owners must integrate it with real deployment paths for mandatory enforcement. Do not claim performance gains without same-input bare-vs-lite repeated runs. Do not conflate CI green with deployment and production success.

Sources: https://zenn.dev/luvtechno/articles/isucon2026-preparation ; https://zenn.dev/luvtechno/articles/isucon2026-competition-day ; https://code.claude.com/docs/en/cli-reference ; https://code.claude.com/docs/en/settings ; https://code.claude.com/docs/en/permissions ; https://code.claude.com/docs/en/hooks
