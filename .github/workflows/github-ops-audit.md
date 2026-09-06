---
on:
  workflow_dispatch:

permissions:
  contents: read
  issues: read
  pull-requests: read
  actions: read
  copilot-requests: write

engine:
  id: copilot
  model: claude-haiku-4.5

tools:
  github:
    toolsets: [repos, issues, pull_requests, actions]
    allowed-repos:
      - "kafka2306/*"
    min-integrity: approved

safe-outputs:
  create-issue:
    max: 1
    target-repo: "*"
    github-token: ${{ secrets.DASHBOARD_GITHUB_TOKEN }}
    deduplicate-by-title: true
  add-comment:
    max: 1
    target: "*"

tracker-id: kafka2306-ops-audit
timeout-minutes: 15
max-turns: 8
---

# KAFKA2306 public GitHub operations audit

Audit the current public GitHub state under KAFKA2306 and route at most one actionable gap.

## Authority

1. Read the current `KAFKA2306/agent-resources` `AGENTS.md`.
2. Read `KAFKA2306/agent-resources#352` and its current referenced canonical issues.
3. Treat current owner repository state, GitHub Actions, deployment and production as stronger evidence than historical prose.

## Scope

- Public repositories under `KAFKA2306` only.
- Do not read or expose private repository content.
- Do not mutate code, branches, settings, rulesets, deployments or secrets.
- Do not use shell `git push`, merge, deploy, or repository-setting mutations.

## Run contract

1. Re-read current GitHub state and existing open issues/PRs before deciding anything.
2. Select at most one current blocker with clear user or operational value.
3. Search the correct owner repository for an existing canonical issue before creating anything.
4. If an existing canonical issue already owns the same decision and uncertainty:
   - do not create a duplicate;
   - only when the current repository is `KAFKA2306/agent-resources` and the state changed materially, use `add_comment` to add one short evidence update to that existing issue;
   - otherwise perform no write.
5. Create one issue only when all are true: current evidence exists, no duplicate exists, owner repository is clear, next action is bounded, completion criteria exist, and verification is concrete.
6. New issue bodies must start with: 目的, Current state, Next action, Completion criteria, Verification.
7. Use real GitHub identity `owner/repo#number` and canonical URLs. Never invent log-only issue numbers.
8. Classify claims only as VERIFIED, OBSERVED, INFERRED, or UNVERIFIED. Never mark an aggregate handoff VERIFIED.
9. If no actionable gap exists, finish successfully with zero writes.

## Push-trigger proof rule

When the event is a push caused by installing or updating this workflow, this is a proof run. Do not create any issue. Verify that #297, #319, #340 and #352 are not duplicated. If this workflow installation is a material state change for #352, add exactly one concise comment to `KAFKA2306/agent-resources#352` with the run URL and directly observed evidence. Otherwise write nothing.
