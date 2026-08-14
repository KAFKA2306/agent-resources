# Agent Resources

A package manager for AI agents. 

## Commands

This project uses `uv` for Python environment management. **Always use `uv run` to execute Python commands** to ensure they run in the correct virtual environment.

```bash
# Run tests
uv run pytest

# Run linters/formatters
uv run ruff check .
uv run ruff format .

# Run type checker
uv run ty check

# Test the CLI tools
uv run agr --help
uv run agrx --help
```

## Architecture
...

## agr.toml Format

The configuration file uses a flat array of dependencies:

```toml
dependencies = [
    {handle = "username/repo/skill", type = "skill"},
    {handle = "username/skill", type = "skill"},
    {path = "./local/skill", type = "skill"},
]
```

Each dependency has:
- `type`: Always "skill" for now
- `handle`: Remote GitHub reference (username/repo/skill or username/skill)
- `path`: Local path (alternative to handle)

Future: A `tools` section will configure which tools to sync to:
```toml
tools = ["claude", "cursor"]
```

## Code Style
...

## Boundaries

### Always Do
- agr and agrx should always be unified and synced.
- include in the plan to write tests for what is implemented
- Save all skills in `skills/` directory (not `.claude/skills/` which is gitignored)

### Ask First
...

### Never Do
...

## GitHub write reliability contract

GitHub mutations must use a narrow, state-verified sequence. The goal is to make each write deterministic, reversible where possible, and easy to resume after a connector-side rejection.

1. **Read before every state transition.** Re-fetch the repository, target branch/PR/Issue, and relevant CI state immediately before the write. Do not rely on an earlier snapshot after another mutation has occurred.
2. **Use one canonical work line.** Reuse the existing canonical branch and PR when one exists. Before creating a branch or PR, verify that the same branch/PR does not already exist. Never create duplicate recovery branches or PRs.
3. **Make one mutation at a time.** Do not issue parallel writes to the same repository state. After each successful mutation, re-read the resulting state before the next mutation.
4. **Pin destructive or irreversible actions to current state.** Merge only when the exact PR head SHA has the required CI green, and pass that expected head SHA to the merge action when supported. Never force-push or direct-push as a workaround for a rejected merge.
5. **Treat host-side safety rejection as transient, not as an authentication diagnosis.** If a mutation is rejected before GitHub executes it, re-read the target state and retry the exact same canonical action once. Do not switch to a broader or more destructive action to bypass the rejection.
6. **After a second host-side rejection, stop mutations for that run.** Preserve the single canonical branch/PR, record the blocker and next action, and resume from fresh state on the next run. Do not loop, fabricate success, or leave a partial alternative work line.
7. **Distinguish GitHub errors from connector safety rejection.** GitHub API responses such as mergeability/branch-protection/conflict errors require fixing the repository state. A host-side pre-execution rejection requires the bounded recovery sequence above; it is not evidence that GitHub credentials expired.
8. **Separate merge and cleanup.** After merge succeeds, re-fetch `main`, PR state, Issue state, and branch state. Then perform cleanup as separate verified mutations. Delete only branches proven merged/superseded and never delete the canonical unfinished branch.
9. **Prefer idempotent continuation.** A later run should be able to observe that a prior step already succeeded and continue from the next step without repeating completed writes.
10. **Report evidence, not assumptions.** Record the target URL, exact head/merge commit SHA, CI result, mutation result, cleanup result, and any remaining blocker.

This contract does not bypass ChatGPT/OpenAI safety controls. It minimizes ambiguous or unnecessarily broad mutations so legitimate writes are easier to evaluate and recover safely.

## Security
...

# Docs

General
https://agentskills.io/
https://agents.md/

Claude Code:
https://code.claude.com/docs/en/skills
https://code.claude.com/docs/en/slash-commands
https://code.claude.com/docs/en/sub-agents
https://code.claude.com/docs/en/memory

Cursor:
https://cursor.com/docs/context/skills
https://cursor.com/docs/context/commands
https://cursor.com/docs/context/subagents
https://cursor.com/docs/context/rules

GitHub Copilot:
https://docs.github.com/en/copilot/concepts/agents/about-agent-skills

Codex:
https://developers.openai.com/codex/skills
https://developers.openai.com/codex/custom-prompts/

Open Code:
https://opencode.ai/docs/skills
https://opencode.ai/docs/commands
https://opencode.ai/docs/agents/