---
name: issue-resolution-router
description: Route repository issue resolution across independent Codex evidence lanes. Use when an issue may benefit from parallel exploration, adversarial review, or independent verification before implementing, merging, or closing work.
---

# Issue Resolution Router

Resolve the issue to the smallest evidence-backed outcome.

## Route first

Read the repository instructions and current state before delegating.

Keep the task in the parent agent when it is a small, direct edit or a sequential task whose next step depends tightly on the previous one.

Use parallel Codex agents only when the work cleanly decomposes into independent evidence lanes. Prefer these skills:

- `$issue-explorer` for competing explanations or solution paths.
- `$issue-critic` for an independent attempt to falsify the leading path.
- `$issue-verifier` for direct acceptance evidence.

Do not create agents merely to increase agent count.

## Shared rules

- Prefer current code, config, tests, CI, runtime evidence, and canonical repository instructions over historical prose.
- Prefer DELETE > MERGE > REPLACE > ADD.
- Reuse existing Issues, PRs, branches, workflows, schemas, and authorities when possible.
- Do not make business outcomes, third-party adoption, external buyer behavior, or unavailable human actions completion blockers.
- Separate repository acceptance from merge, deployment, release, production, device, and external outcomes.
- Treat unobserved state as UNVERIFIED, not success.

## Integration

The parent agent owns the final decision and writes.

Compare independent findings, reject unsupported branches, implement the smallest supported change, run the minimum meaningful checks, and read back the resulting state.
