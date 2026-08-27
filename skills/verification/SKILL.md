---
name: verification
description: Independently verify artifacts, runtime behavior, APIs, deployments, releases, and production outcomes using direct evidence rather than implementation claims.
---

# Verification

Use this skill when success depends on an observable state outside the edit itself.

## Contract

1. State the exact outcome that must be true.
2. Select the closest direct observation: executable test, produced artifact, API response, deployed page, runtime log, database state, release asset, or production behavior.
3. Reproduce the observation from the current state. Do not substitute issue text, documentation, a commit, a pull request, or CI success for the requested outcome.
4. Record enough evidence to distinguish pass, fail, partial pass, and not verified.
5. If verification fails, identify whether the failure is implementation, environment, deployment, data, permission, or observability related. Fix it when it is within scope and verify again.
6. Never fabricate unavailable evidence or silently fall back to synthetic data when real data is required.

## Independence

Verification should test the contract, not merely repeat the implementation's internal assumptions. Prefer a separate read path, consumer-facing interface, or externally observable artifact when practical.

## Completion states

Use ordinary terms: implemented, tested, merged, deployed, production verified, failed, or not verified. Do not invent maturity levels.
