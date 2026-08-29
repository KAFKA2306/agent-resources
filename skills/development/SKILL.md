---
name: development
description: End-to-end repository development: inspect the current implementation, choose the smallest solution, implement it, verify behavior, review the diff, commit, and verify release or production state when required.
---

# Development

Use this skill for repository changes. Do not split one engineering task into separate research, planning, review, commit, documentation, and release skills unless an independent domain contract requires it.

## Context budget

Start from the repository `AGENTS.md` and the exact task surface. Do not preload the whole repository, all docs, all Issues, all PR history, or historical conversation.

For each workline keep only:

1. requested outcome;
2. files/config/data that own it;
3. current evidence/blocker;
4. nearest verifier;
5. one next action or completion condition.

Load additional context only when the current evidence proves it is needed. Prefer canonical code/config/schema/workflow/Issue links over copying their contents into a new summary. If work spans agents or context windows, persist the current state and one exact next action in the existing Issue/PR or canonical artifact; do not rely on chat memory or create a parallel agent-state database.

## Contract

1. Inspect the current repository state before deciding what to change. Read only the implementation, configuration, tests, workflows, Issue/PR, or evidence that materially affect the task.
2. Treat current code and runtime state as stronger evidence than stale documentation or historical issue text.
3. Identify the root cause and the smallest implementation that satisfies the requested external outcome. Prefer standard APIs, existing libraries, existing repository patterns, and deletion over new abstraction.
4. Implement the change. Update documentation only when the current implementation makes it inaccurate.
5. Run the narrowest relevant tests first, then repository quality checks needed for the affected surface.
6. Review the actual diff for regressions, unrelated changes, duplicated logic, defensive code that hides failures, stale files, and unverifiable claims.
7. Commit only coherent, verified work. Keep generated or unrelated changes out of the commit.
8. When the requested outcome includes CI, deployment, release, an API, a page, or another external state, verify that state directly. A green local test or CI run is not evidence that production works.

## Planning and solution selection

Plan only to reduce execution risk. A useful plan names concrete owners, dependencies, completion conditions, and verification. Do not create planning artifacts when implementation is already obvious and bounded.

When several solutions are plausible, compare them against the requested outcome, current architecture, operational cost, dependencies, and failure modes. Avoid implementation techniques becoming goals in themselves.

## Review and completion

Review correctness before style: data ownership, state transitions, error semantics, concurrency, compatibility, security boundaries, tests, and observable user behavior as applicable. Prefer executable evidence over comments.

Do not report completion until the requested state is demonstrated. Distinguish implemented, tested, merged, deployed, and production-verified states when they differ.
