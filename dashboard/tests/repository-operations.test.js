import assert from "node:assert/strict";
import test from "node:test";

import { summarizeRepositoryOperations } from "../../docs/dashboard/repository-operations.js";

test("repository operations summary reports explicit classification coverage", () => {
  const summary = summarizeRepositoryOperations({
    generatedAt: "2026-08-21T00:00:00Z",
    repositories: [
      { classification: { domain: "agent-web" } },
      { classification: { domain: null } },
      { classification: { domain: "finance" } },
    ],
  });

  assert.equal(summary.generatedAt, "2026-08-21T00:00:00Z");
  assert.equal(summary.repositoryCount, 3);
  assert.equal(summary.classifiedCount, 2);
  assert.equal(summary.unclassifiedCount, 1);
  assert.match(summary.generatedLabel, /2026/);
});

test("repository operations summary rejects missing provenance", () => {
  assert.throws(
    () => summarizeRepositoryOperations({ repositories: [] }),
    /missing generatedAt/,
  );
});
