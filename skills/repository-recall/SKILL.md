---
name: repository-recall
description: |
  Find the correct KAFKA2306 public repository from a remembered requirement or feature.
  Use when the user says "which repo", "that Unity feature", cannot remember a repository name,
  or asks where an existing public project or function lives.
---

# Repository Recall

Use the public repository recall index before searching all repositories.

Canonical index:

`dashboard/data/repository-index.json`

Canonical repository:

`https://github.com/KAFKA2306/agent-resources`

## Rules

1. Search only the index of `KAFKA2306` repositories that are public and non-archived.
2. Do not infer a repository from its name alone.
3. Evaluate `purpose`, `matches`, and `notFor` together.
4. Treat `needsReview: true` as stale or unverified semantic metadata. It may be shown as a candidate but must not be asserted as the answer without checking its public source evidence.
5. If the index does not identify a repository, say it is unresolved from the public index. Do not guess or reveal private repository names.
6. Only after choosing a repository should you read that repository's README, code, Issues, or pull requests in depth.
7. If fallback discovery is necessary, search public GitHub repositories only, then update the index rather than relying on conversation memory.

## Preferred command

From an `agent-resources` checkout:

```bash
python -m dashboard.repository_recall search "<requirement>"
```

The command returns:

- `selected`: a repository name only when the evidence is strong enough
- `ambiguous`: whether the query remains unresolved
- `candidates`: scored public candidates with positive and negative matching reasons
- `sources`: public GitHub evidence URLs used by the index

## Decision procedure

### Selected result

When `selected` is non-null:

1. Confirm the selected entry is not `needsReview`.
2. Follow its `sources` URLs if the user needs current details.
3. Continue work in that repository.

### Ambiguous result

When `selected` is null:

1. Inspect the top public candidates and their `reasons` / `exclusions`.
2. If one candidate can be verified from its public source evidence, use it.
3. Otherwise report that the public index cannot identify the repository yet.
4. Do not substitute a private project from memory.

## Unity regression examples

These public repositories have intentionally different roles:

- `unity-mcp`: general Unity Editor control through Model Context Protocol.
- `unity-agent`: VRChat avatar editing such as Expression Menu and PhysBone.
- `UnityMCP-VRC`: VRChat world creation and UdonSharp-oriented support.

Examples:

- `Expression Menu / PhysBone` → `unity-agent`
- `UdonSharp world` → `UnityMCP-VRC`
- `Unity scene/assetsをLLMから操作` → `unity-mcp`
- `Unityのあの機能` → ambiguous unless more evidence is available
- a requirement with no public indexed match → unresolved; do not disclose a private repository

## Refresh boundary

The index is refreshed by `.github/workflows/repository-recall-refresh.yml`.
Source changes mark semantic data for review instead of silently treating old meaning as current.
