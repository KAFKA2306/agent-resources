---
name: development
description: End-to-end repository development: inspect the current implementation, choose the smallest solution, implement it, verify behavior, review the diff, commit, and verify release or production state when required.
---

# Development

Use this skill for repository changes. Do not split one engineering task into separate research, brainstorming, design, planning, review, commit, documentation, and release skills unless a genuinely independent domain contract requires it.

## Contract

1. Inspect the current repository state before deciding what to change. Read the implementation, configuration, tests, workflows, issues or pull requests that materially affect the task.
2. Treat current code and runtime state as stronger evidence than stale documentation or historical issue text.
3. Identify the root cause and the smallest implementation that satisfies the requested external outcome. Prefer standard APIs, existing libraries, existing repository patterns, and deletion over new abstraction.
4. Implement the change. Update documentation only when the current implementation makes it inaccurate.
5. Run the narrowest relevant tests first, then repository quality checks needed for the affected surface.
6. Review the actual diff for regressions, unrelated changes, duplicated logic, defensive code that hides failures, stale files, and unverifiable claims.
7. Commit only coherent, verified work. Keep generated or unrelated changes out of the commit.
8. When the requested outcome includes CI, deployment, release, an API, a page, or another external state, verify that state directly. A green local test or CI run is not evidence that production works.

## Planning

Plan only to reduce execution risk. A useful plan names concrete files or components, dependencies, completion conditions, and verification. Do not create planning artifacts when the implementation is already obvious and bounded.

## Solution selection

When several solutions are plausible, compare them against the requested outcome, current architecture, operational cost, dependencies, and failure modes. Avoid implementation techniques becoming goals in themselves.

## Review

Review correctness before style. Check data ownership, state transitions, error semantics, concurrency, compatibility, security boundaries, tests, and observable user behavior as applicable. Prefer evidence from executable behavior over comments.

## Completion

Do not report completion until the requested state is demonstrated. Distinguish explicitly between implemented, tested, merged, deployed, and production-verified states when they differ.
