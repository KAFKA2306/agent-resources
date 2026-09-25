# Issue Resolution Collaboration

Codex plugin for evidence-driven issue resolution.

It follows the current OpenAI plugin layout:

- `.codex-plugin/plugin.json`
- `skills/<skill-name>/SKILL.md`
- `skills/<skill-name>/agents/openai.yaml`

## Workflow

Use `$issue-resolution-router` as the parent workflow.

The router should keep simple work inline. When the problem cleanly decomposes, use Codex parallel agents for independent lanes:

- `$issue-explorer`: generate competing explanations and minimal resolution paths
- `$issue-critic`: try to falsify the leading resolution
- `$issue-verifier`: check completion conditions against direct evidence

The parent Codex agent integrates the results and owns writes. For concurrent code changes, use Codex worktree isolation rather than sharing one mutable checkout.

## Completion rule

Only mechanically verifiable conditions available to the current executor are blockers. External adoption, sales, buyer activity, unavailable human actions, and third-party outcomes may be observations but are not close blockers.
