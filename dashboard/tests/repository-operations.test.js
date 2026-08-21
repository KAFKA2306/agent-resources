import assert from "node:assert/strict";
import test from "node:test";

import {
  loadRepositoryOperations,
  summarizeRepositoryOperations,
} from "../../docs/dashboard/repository-operations.js";

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

test("repository operations falls back to the persisted GitHub Pages snapshot", async () => {
  const requests = [];
  const elements = new Map([
    ["operations-generated-at", { dateTime: "", textContent: "" }],
    ["operations-summary", { textContent: "" }],
  ]);
  const documentRef = {
    getElementById(id) {
      return elements.get(id) ?? null;
    },
  };
  const payload = {
    generatedAt: "2026-08-21T00:00:00Z",
    repositories: [
      { classification: { domain: "agent-web" } },
      { classification: { domain: null } },
    ],
  };
  const fetchImpl = async (url) => {
    requests.push(url);
    if (requests.length === 1) return { ok: false, status: 404 };
    return { ok: true, status: 200, async json() { return payload; } };
  };

  await loadRepositoryOperations({ fetchImpl, documentRef });

  assert.deepEqual(requests, [
    "./repository-operations.json",
    "https://kafka2306.github.io/agent-resources/dashboard/repository-operations.json",
  ]);
  assert.equal(elements.get("operations-generated-at").dateTime, payload.generatedAt);
  assert.match(elements.get("operations-generated-at").textContent, /Operations snapshot:/);
  assert.equal(elements.get("operations-summary").textContent, "Operations: 2 repos · 1 classified · 1 unclassified");
});
