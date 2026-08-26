---
name: bibliographic-research
description: Verify and normalize bibliographic data in KAFKA2306 research/data/knowledge repositories using primary publisher, library, DOI, ISBN, or standards evidence. Use for repeated title normalization, Work/Edition identity review, provenance-preserving metadata correction, grouped bibliographic review, migration identity checks, and throughput benchmarking. Do not use for finance, VR/3D, games, platform operations, or generic documentation work.
---

# Bibliographic Research

Turn bibliographic anomalies into source-backed, reusable data corrections while minimizing repeated research and PR/CI overhead.

## Scope

Use this skill when the active repository contains bibliographic or publication metadata and the work repeats across multiple records.

Typical tasks:

- normalize titles, subtitles, volume metadata, imprints, series labels, and commercial annotations;
- distinguish Work, Edition, Holding, adaptation, reissue, translation, and format identities;
- review duplicate or ambiguous Works;
- preserve ISBN, ASIN, DOI, publisher identifiers, source URLs, and acquisition provenance;
- batch low-ambiguity records by publisher or series;
- measure whether batch review reduces research and delivery time without weakening validation.

Do not use this skill to guess canonical metadata from marketplace strings or to merge Works because titles merely look similar.

## Start from current state

1. Read the repository's current branch, open canonical Issue/PR, relevant schemas, loaders, validation code, tests, generated artifacts, CI, and publication state.
2. Run or inspect the repository's existing anomaly/audit commands before inventing a new detector.
3. Reuse the repository's current normalization, merge, and identity overlays. Do not create a parallel metadata authority.
4. If a canonical PR or Issue already covers the same data state, continue it rather than starting a duplicate workline.

## Group before researching

Prefer grouped review when records share a stable research surface such as:

- publisher or imprint;
- series/base title;
- creator;
- source catalog or identifier namespace;
- the same anomaly class.

Grouping is only a research-prioritization mechanism. It must not itself change Work identity.

Prioritize groups that maximize accepted records per primary-source lookup while remaining low ambiguity. Keep adaptations, translations, old/new editions, split chapters, free samples, omnibus editions, and same-title distinct Works separate until primary evidence resolves them.

## Primary evidence

Use the strongest available source for the claim being changed.

Preferred order:

1. official publisher/product catalog or official creator publication record;
2. national library or authoritative library catalog;
3. DOI/Crossref or equivalent publication registry for scholarly works;
4. formal standards such as IFLA LRM, RDA, MARC, BIBFRAME, ISBN specifications, or repository-domain standards;
5. secondary sources only when primary evidence is unavailable, with that limitation recorded.

For every accepted correction, preserve enough provenance to reconstruct why the change was made: source URL or identifier, source title/field, review method, and the affected repository identity.

## Identity rules

Treat title text as descriptive metadata, not sufficient identity evidence.

- Preserve Work, Edition, Holding, and source-record identities unless evidence supports a specific change.
- Never merge Works only because normalized titles collide.
- Use explicit evidence such as creator, work type, adaptation relation, ISBN/DOI ownership, publisher metadata, language, edition statement, or publication history when identity matters.
- If multiple candidate identities remain possible, fail closed and persist or report the ambiguity instead of selecting one arbitrarily.
- Preserve null as null. Do not convert missing evidence to strings, defaults, inferred dates, inferred units, or fabricated identifiers.
- Preserve units, periods, language/script distinctions, edition statements, and identifier namespaces exactly enough for reproducibility.

## Separate safe normalization from identity changes

Use two work classes:

### Safe descriptive normalization

Examples:

- remove volume numbers from a Work title when the publisher clearly treats them as volume metadata;
- separate imprint/series suffixes from Work title;
- remove marketplace-only annotations such as electronic-only bonuses or preview labels when primary evidence shows they are edition/distribution attributes;
- restore publisher-official punctuation or subtitle boundaries.

These may be handled in a publisher/series batch when each record has independent primary evidence.

### Identity-affecting changes

Examples:

- merging two Works;
- splitting one Work;
- linking adaptation-of relationships;
- choosing among same-title Works;
- assigning an Edition to a different Work.

Handle these separately and require stronger evidence plus targeted regression tests.

## Use repository automation

Deterministic work belongs in repository scripts and CI, not in prose-only manual steps.

When available, use existing commands that:

- generate anomaly or review batches;
- validate normalization partition/schema shape;
- detect title-key or Work-identity collisions;
- materialize API/data artifacts;
- run migration/precheck diagnostics;
- execute tests and distribution smoke checks.

If the same deterministic operation is repeatedly missing, add one small repository script rather than expanding this skill with copied code.

## Throughput measurement

Do not claim batch review is faster merely because fewer PRs were opened.

When enough comparable records exist, measure direct throughput:

- reviewed records;
- accepted records;
- rejected/ambiguous records;
- elapsed review time;
- total elapsed time per accepted record;
- primary-source lookups per accepted record;
- PRs and CI runs per 10 accepted records;
- collision count;
- regression failures.

Use `minutes/accepted record` or `accepted records/hour` as the primary speed metric. Treat reduced PR/CI count as a contributor, not a proxy for total time.

Preserve benchmark inputs and results in a machine-readable repository artifact when the repository has an active throughput workline.

## Stop conditions

Stop researching a record when the available primary evidence is sufficient to support the exact proposed change and identity is no longer ambiguous.

Do not keep searching for redundant sources solely to increase citation count. Escalate or leave unresolved when additional evidence would be required to distinguish identities safely.

## Validation before merge

Before considering a bibliographic change mergeable, verify the exact PR head against the repository's relevant checks and confirm:

- primary-source provenance exists for every accepted record;
- schema/data validation passes;
- title-key and Work-identity collision behavior is intentional and passes;
- Work/Edition/Holding counts change only when explicitly intended;
- raw/source provenance records are not silently destroyed;
- null semantics and identifiers remain intact;
- generated reusable artifacts are reproducible;
- tests and distribution/build checks covering the changed surface pass.

CI success proves only the checks actually run at that SHA. Verify deployment/publication separately when the task claims a published artifact.

## Completion report

Report only the information needed to judge research and economic value:

- economic/research outcome Before→After;
- primary sources;
- reusable artifact/result;
- grounded monetization or cost-saving path;
- PR/CI/merge/publication state;
- next highest-value research problem.

For batch work, include the direct throughput result when measured. Do not report a speedup factor without comparable elapsed-time evidence.
