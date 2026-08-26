---
name: finance-cross-repo-router
description: |
  Audit finance repositories for cross-repository ownership conflicts and route work to one canonical owner.
  Use when a finance dataset, financial fact, model output, publication path, or release decision spans multiple repositories.
  Do not use for ordinary repository-local bugs, feature implementation, or simple market/news lookup.
---

# Finance Cross-Repository Router

Keep one semantic authority for each finance dataset, fact family, model output, and release decision.

## Procedure

1. Inspect current GitHub state before relying on Issues, documentation, or memory. Read relevant code, configuration, workflows, open PRs, merged changes, and publication paths as needed.
2. Identify the concrete object whose authority may be duplicated: dataset, financial fact, model output, derived evidence, publication artifact, or release decision.
3. Determine the canonical owner from current implementation and explicit repository contracts. Use primary financial sources when the ownership decision depends on external financial facts.
4. Detect only cross-repository problems: duplicated collection or validation semantics, competing publishers, duplicated model/evaluation authority, conflicting freshness rules, or conflicting release decisions.
5. Rank findings by economic or decision impact. Prefer issues that can change an investment decision, corrupt reproducibility, create material data cost, or cause divergent published evidence.
6. Route implementation to the canonical repository agent. A transport/cache repository may own generic transfer, storage, hashing, or manifest mechanics, but must not acquire dataset-specific semantics merely because it transports the artifact.
7. Report merge state and release/publication state separately. Never infer release success from a merged PR or passing CI.
8. Verify the requested external state when possible: published artifact exists, provenance/hash is fixed, and remote read-back succeeds.

## No-op rule

No-op is a successful result.

Do not create or repeat an Issue, PR, or comment when:

- no cross-repository authority conflict exists;
- the finding is repository-local;
- the same unresolved conflict is already recorded and GitHub state has not materially changed;
- only wording or documentation differs while implementation authority is unambiguous.

Material change means a relevant merge, close/reopen, code/workflow/configuration change, publication-state change, owner-contract change, or new conflicting implementation.

## Routing rules

- Exactly one repository owns dataset-specific collection semantics, validation, freshness, and release decisions.
- Exactly one repository owns each domain-specific model/evaluation output.
- Shared infrastructure owns only generic mechanics unless its explicit domain contract says otherwise.
- Consumers read canonical artifacts or APIs instead of cloning another repository to become a second publisher.
- Prefer deletion or reuse over adding adapters, duplicate writers, or parallel pipelines.

## Output

Return only decision-relevant information:

- economic / decision impact;
- evidence and current GitHub state;
- affected repositories;
- canonical owner and conflicting owner, if any;
- merge state;
- release/publication verification state;
- next repository agent/action.

If there is no material cross-repository problem, return a concise no-op result instead of generating work.

## Boundary with other skills

Use `repository-recall` only to locate the correct repository when its identity is unknown. After repositories are known, this skill owns finance-specific cross-repository authority routing. Code review, implementation, and release execution remain with their respective skills or repository agents.
