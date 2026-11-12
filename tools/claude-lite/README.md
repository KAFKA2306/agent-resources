# Claude Code HOOTL lite runner (WSL/Linux)

A reusable, **opt-in** runner for evaluating autonomous coding tasks without changing the source checkout. It adds only a temporary clean clone, isolated config, narrow permissions, a pre-deploy git guard, a score-stall audit reminder, a final-window reminder, and a compaction reminder. It does **not** replace the owner repository's `AGENTS.md`, CI, or deploy authority.

## Use

Requires `git`, `python3`, a compatible current `claude` CLI, plus `bubblewrap` and `socat` for the Linux/WSL2 sandbox. Log in once with the dedicated config directory, for example `CLAUDE_CONFIG_DIR="$HOME/.agent-eval/claude-config" claude auth login`. The runner clears inherited environment variables so host GitHub/cloud/provider credentials are not passed into the agent subprocess; authenticate its dedicated Claude profile interactively once. Sandboxing is fail-closed if unavailable. The runner does not perform login, pay for API calls, deploy, or modify the host/source checkout on its own.

```bash
# Run from any directory; the three paths/values are arguments, not defaults.
./tools/claude-lite/run.sh \
  "$HOME/projects/my-project" \
  "$HOME/my-conditions.md" \
  '2026-11-14T18:00:00+09:00'
```

`my-conditions.md` supplies the authorized work, success condition, baseline/evaluation data, time limit, external side-effect bounds and permitted test/deploy operations. Use a path outside the source repository for confidential conditions. A run lives in `~/.agent-eval/runs/run-*/repo` and logs to its own stdout. It refuses to start from a dirty source checkout. It never merges the cloned changes back automatically; inspect and apply them through the owner repository's usual PR flow.

## Owner-repo integration

The runner's `make bench` convention requires its stdout to contain `AGENT_SCORE=<number>` on a line when a comparable score exists. The `PostToolUse` hook sees only successfully completed Bash tools. Without that output, stall detection is not activated. Only improvements reset the timer; after 30 minutes without improvement an independent audit subagent is *suggested*, not directly launched. In the final 40 minutes before the specified deadline a one-time reminder requests restart, persistence and final-run validation. The reminder can only fire on a later successful Bash tool call; a crashed or idle agent cannot be resurrected by this hook.

For deploy and benchmark jobs, implement a real entrypoint-level guard in each owner repo's Makefile. Example (adapt an existing target; do not introduce a second deploy authority):

```make
.PHONY: check-clean
check-clean:
	@test -z "$$(git status --porcelain)" || { echo 'Commit before deployment' >&2; exit 1; }

# In an existing Makefile, add `check-clean` as a prerequisite
# to existing `deploy` / `bench` targets; do not overwrite their recipes.
```

The `PreToolUse` hook also blocks an uncommitted exact `make bench` or `make deploy` call. **By default `make deploy` is not allowed**: add it to the run-specific permission allowlist only when the target and external effects are authorized and its own Makefile guard is installed. It **does not** protect all possible deploy entrypoints or underlying OS processes. `permissions.block*OutsideWorkingDirectories` restricts built-in file tools, not arbitrary Bash subprocesses. Claude Code sandboxing is enabled and refuses unsandboxed Bash execution. For untrusted code, still run the full agent inside an actual container/VM with filesystem, network and credentials isolated. Do not use `--dangerously-skip-permissions`.

## Isolation and evaluation contract

- `CLAUDE_CONFIG_DIR` moves user config/plugins/history to a dedicated location; `--setting-sources ''` excludes user/project/local settings. `--strict-mcp-config` with an empty `mcpServers` config excludes configured MCP servers (check effective settings after Claude Code updates). Managed policy cannot be bypassed.
- The clone is outside the source repository's parent tree, avoiding ancestor `CLAUDE.md` inheritance. The **cloned repository's own** tracked `CLAUDE.md` and code remain task inputs, so this is not a no-instructions baseline and not a security sandbox. Use the same source commit and task inputs for bare-versus-lite comparison.
- Permissions are `dontAsk`: unlisted commands are denied rather than prompting, so a run can fail visibly instead of hanging for approval. Change the allow rules only after reviewing the owner's actual approved commands and limits.
- A single best score is not sufficient to claim improvement. Compare same-task, same-evaluator, same-source-revision run success, final score, elapsed time, failures, and cost across repeated runs. Record the exact revision and outcome in the existing PR/Issue rather than building another status database.
- A `PostToolUse` hook cannot enforce hard timeouts, agent liveness, restore commits, or guarantee final state. The outer supervisor and native `make`/deploy mechanisms must enforce those. This runner is a runnable example, not proof that HOOTL operations are already active on your machines.

## Primary references

- [ISUCON2026 winner, preparation](https://zenn.dev/luvtechno/articles/isucon2026-preparation)
- [ISUCON2026 winner, competition day](https://zenn.dev/luvtechno/articles/isucon2026-competition-day)
- [Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference)
- [Claude Code settings/precedence](https://code.claude.com/docs/en/settings)
- [Claude Code permissions](https://code.claude.com/docs/en/permissions)
- [Claude Code hooks reference](https://code.claude.com/docs/en/hooks)