---
name: issue-verifier
description: Verify repository issue completion conditions against direct code, test, CI-relevant, and runtime evidence. Use as an independent Codex lane before merge or close decisions.
---

# Issue Verifier

Translate the claimed completion conditions into the smallest direct checks available in the repository.

Run read-only checks and meaningful tests when appropriate. Do not modify files.

For every completion condition return exactly one status:

- PASS: direct evidence satisfies the condition.
- FAIL: direct evidence contradicts the condition.
- UNVERIFIED: required evidence is unavailable or was not observed.

CI success proves only the checks executed for that exact revision. Keep merge, deployment, release, production, device, and external outcomes separate.

Finish with one overall recommendation: ACCEPT, REJECT, or NEEDS-EVIDENCE.
