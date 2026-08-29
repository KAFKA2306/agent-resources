import assert from "node:assert/strict";
import test from "node:test";

import {
  loadRepositoryOperations,
  renderRepositoryOperationsSummary,
  summarizeRepositoryOperations,
} from "../../docs/dashboard/repository-operations.js";

test("repository operations summary reports repository count only", () => {
  const summary = summarizeRepositoryOperations({
    generatedAt: "2026-08-21T00:00:00Z",
    repositories: [{ name: "alpha" }, { name: "beta" }, { name: "gamma" }],
  });

  assert.equal(summary.generatedAt, "2026-08-21T00:00:00Z");
  assert.equal(summary.repositoryCount, 3);
  assert.equal(Object.hasOwn(summary, "classifiedCount"), false);
  assert.equal(Object.hasOwn(summary, "unclassifiedCount"), false);
  assert.match(summary.generatedLabel, /2026/);
});

test("repository operations summary rejects missing provenance", () => {
  assert.throws(
    () => summarizeRepositoryOperations({ repositories: [] }),
    /missing generatedAt/,
  );
});

test("repository operations UI has no repository classification action", () => {
  const elements = new Map([
    ["operations-generated-at", { dateTime: "", textContent: "" }],
    ["operations-summary", { textContent: "" }],
  ]);
  const documentRef = {
    getElementById(id) {
      return elements.get(id) ?? null;
    },
  };

  renderRepositoryOperationsSummary({
    generatedAt: "2026-08-21T00:00:00Z",
    repositories: [{ name: "alpha" }],
  }, documentRef);

  assert.equal(elements.get("operations-summary").textContent, "Operations: 1 repos");
  assert.equal(documentRef.getElementById("operations-zone-action"), null);
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
    repositories: [{ name: "alpha" }, { name: "beta" }],
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
  assert.equal(elements.get("operations-summary").textContent, "Operations: 2 repos");
});
