---
name: claude-code-operations
description: Operate Claude Code sessions with native background-agent observability, context status lines, explicit long-lived process boundaries, and normalized JSON diffs without weakening repository verification contracts.
---

# Claude Code operations

Use this skill when Claude Code work needs to continue without watching one terminal, when context consumption must be visible, or when a process/session must have an explicit lifecycle.

Prefer current Claude Code built-ins before adding hooks, daemons, dashboards, or terminal-session dependencies. Do not treat Claude's own `done` state as evidence that repository, CI, deployment, or production acceptance criteria passed.

## 1. Observe and detach Claude Code sessions with built-ins

For a Claude Code session that should keep working after the current terminal is released, use the native background-agent supervisor:

```bash
claude --bg "<task>"
claude agents
claude logs <session-id>
claude attach <session-id>
claude stop <session-id>
```

Inside an attached session, `/background` (alias `/bg`) detaches the current session.

`claude agents` / agent view is the default operator surface for session state. Do not create a parallel session-state database or custom log viewer unless an external machine-readable integration has a concrete requirement that the native view cannot satisfy.

Reference: https://code.claude.com/docs/en/agent-view

## 2. Distinguish session-scoped Bash tasks from persistent processes

Claude Code background Bash tasks are useful for test runners, dev servers, builds, and similar commands while the Claude session remains alive. Manage them with `/tasks` (also `/bashes`).

Do not use a Claude Code background Bash task for a process that is required to survive Claude Code exit: Claude Code automatically cleans up those tasks when it exits.

References:
- https://code.claude.com/docs/en/interactive-mode#background-bash-commands
- https://code.claude.com/docs/en/tools-reference

If a non-Claude process truly must outlive the Claude session, use an existing operating-system or project supervisor. Do not add a repository-specific wrapper solely to keep a process alive.

For macOS/Linux/WSL, `zmx` can be evaluated when named terminal-session persistence, scrollback/history, reattach, and explicit kill semantics are required. It is optional, not a baseline dependency. `zmx` does not support native Windows; on Windows prefer an existing WSL workflow when that is already the project's supported execution environment. Do not silently substitute an unverified native-Windows process wrapper.

Reference: https://github.com/neurosnap/zmx

## 3. Use Claude Code's native status line for context visibility

Configure the status line with the built-in `/statusline` command rather than maintaining a dashboard backend only for token/context display:

```text
/statusline show repository name, git branch, model name, and context window usage percentage
```

The status-line JSON already exposes `model`, workspace/cwd fields, and `context_window.used_percentage`. That percentage may be null before the first API response and immediately after `/compact`; a generated/custom status-line script must handle the null state instead of inventing a value.

Reference: https://code.claude.com/docs/en/statusline

Keep the display short. The target information is:

```text
repo | branch | model | context usage
```

Do not add cost, rate-limit, clock, decoration, or a second status authority unless a concrete operator requirement needs it.

## 4. Use hooks only for event-driven integration

Claude Code already exposes lifecycle events such as `Notification`, `PermissionRequest`, `SubagentStart`, `SubagentStop`, `Stop`, and `SessionEnd`.

Use hooks when another system must receive an event or when deterministic policy enforcement is required. Do not add hooks merely to duplicate `claude agents`, `/tasks`, or the status line.

When hooks are used for observability, record only observable lifecycle data needed by the operator, such as event type, session id, timestamp, cwd, tool/process identity, and success/failure/waiting state. Never collect chain-of-thought as an observability feature.

Verify active hooks with `/hooks`.

References:
- https://code.claude.com/docs/en/hooks
- https://code.claude.com/docs/en/hooks-guide

## 5. Normalize JSON only at the Git diff presentation layer

When a tracked Claude settings JSON file produces noisy key-order-only diffs, prefer a Git textconv driver instead of rewriting the file on every run.

Configure the local repository once:

```bash
git config diff.claude-json.textconv "python -m json.tool --sort-keys"
```

Then mark only the tracked Claude settings path in `.gitattributes`, for example:

```gitattributes
.claude/*.json diff=claude-json
```

Python's JSON formatter sorts object keys for the diff view while leaving the working-tree file unchanged. A key reordering alone should then produce an empty Git diff; a value change must remain visible.

Do not apply a global JSON formatter to unrelated repository JSON files just to solve Claude settings noise.

## 6. Verification

Before reporting this operating setup as working, verify the layer actually changed:

1. `claude --version` reports the installed version used for the test.
2. Start or detach a background Claude session and confirm it appears in `claude agents`.
3. Confirm `claude logs <id>` and `claude attach <id>` can retrieve the same session; stop it explicitly if it is no longer needed.
4. For a session-scoped Bash task, confirm `/tasks` sees it and do not claim it survives Claude exit.
5. Configure the status line and confirm repo/branch/model/context are visible after an API response.
6. Run `/hooks` before relying on a hook-derived event.
7. If JSON diff normalization is configured, test both key-order-only and real-value changes.
8. Run the repository's own test/CI/release/production verification separately. Claude session state is not product acceptance evidence.

If the current environment cannot execute Claude Code itself, mark these runtime checks `UNVERIFIED`; repository documentation or configuration presence alone is not a runtime PASS.
