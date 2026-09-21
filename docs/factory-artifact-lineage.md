# Factory artifact lineage

Software Factory artifact evidence is valid only when it is tied to the exact source revision that produced it.

`dashboard.artifact_lineage.verify_artifact_lineage` accepts artifact records with `path`, `revision`, and lowercase 64-character `sha256`. Verification fails closed when evidence is empty, a path is duplicated, the source revision differs from the expected revision, or the digest is malformed.

This contract is intentionally independent of the artifact producer so APKs, archives, generated indexes, release bundles, and other factory outputs can use the same verifier before release or deployment evidence is accepted.
