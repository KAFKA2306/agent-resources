---
name: skill-development
description: Create, audit, consolidate, simplify, migrate, and retire agent skills while keeping one canonical responsibility per reusable capability.
---

# Skill Development

Use this skill whenever skills themselves are being changed.

## Contract

1. Search existing skills before creating a new one.
2. Merge skills that describe consecutive phases of the same user outcome or repeat the same operational rules.
3. Keep domain-specific skills only when they contain a real domain contract, provider semantics, data model, evaluation rule, or specialized tool workflow that would make a generic skill misleading.
4. Prefer one canonical `SKILL.md` per reusable capability. Treat agent-specific copies and plugin packaging as generated or synchronized distribution surfaces, not independent sources of truth.
5. Move deterministic transformations, validation, parsing, and mechanical checks into scripts when that reduces ambiguity and repeated model reasoning.
6. Delete obsolete skills, references, duplicated scripts, and stale documentation after their useful rules have been absorbed by the canonical skill.
7. Validate the resulting catalog and all references to removed skill names.

## Consolidation test

Two skills should normally be one when a user would reasonably request them as one task, when they share the same inputs and evidence, or when one merely prepares the next. Keep them separate only when independent reuse or a distinct domain contract is demonstrated.

## Migration

When migrating old skill formats, preserve behavior that is still required but do not preserve obsolete structure merely for compatibility. Prefer the current canonical format and update consumers.
