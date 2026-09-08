---
name: issue-resolution-evidence
description: Resolve GitHub/codebase issues by separating exploration, criticism, and verification around current repository evidence.
---

# Issue Resolution Evidence

Use this skill for repository issues that can be resolved from code, tests, CI, runtime evidence, or current repository state.

## Shared contract

- Treat current code, config, tests, CI, runtime evidence, and canonical repository instructions as stronger evidence than historical prose.
- Do not make business outcomes, third-party adoption, sales, external buyer behavior, or unavailable human actions completion blockers.
- Prefer DELETE > MERGE > REPLACE > ADD.
- Reuse an existing canonical Issue, PR, branch, workflow, schema, or authority when one exists.
- Distinguish observed facts from inference. Do not invent unobserved runtime state.
- A candidate is acceptable only when its completion condition is mechanically verifiable with available tools.
- Keep proposed changes minimal. Do not add implementation-mirroring tests for small reversible changes.

## Role protocol

When used by an explorer:
- Produce multiple materially different candidate explanations or resolution paths.
- Include the evidence each candidate would need.
- Do not choose a winner unless evidence already rules alternatives out.

When used by a critic:
- Try to falsify candidate explanations.
- Search for duplicate ownership, stale assumptions, hidden dependencies, regressions, and simpler DELETE/MERGE outcomes.
- Prefer a concrete counterexample over general concern.

When used by a verifier:
- Check the smallest direct acceptance evidence.
- Return PASS, FAIL, or UNVERIFIED for each completion condition with the exact evidence used.
- CI success proves only the checks run for that exact revision; merge, deployment, release, and runtime are separate states.

## Parent integration

The parent agent owns the final decision and any write. It should compare independent findings, choose the smallest supported action, implement it, and then re-run the minimum meaningful verification.
