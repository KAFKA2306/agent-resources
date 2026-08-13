import assert from "node:assert/strict";
import test from "node:test";
import { compareWorkItems, rankRepositories, repositoryHeat } from "../../docs/dashboard/ranking.js";

const generatedAt = "2026-08-13T12:00:00Z";
const repositories = [
  { id: "quiet", name: "quiet", updatedAt: "2026-08-13T11:59:00Z" },
  { id: "waiting", name: "waiting", updatedAt: "2026-08-06T12:00:00Z" },
  { id: "failed", name: "failed", updatedAt: "2026-08-06T12:00:00Z" },
];
function item(repositoryId, lane, updatedAt = generatedAt) { return { repositoryId, lane, updatedAt }; }

test("attention lanes sort before working and done", () => {
  const items = [item("x", "done"), item("x", "working"), item("x", "failed"), item("x", "waiting")];
  items.sort(compareWorkItems);
  assert.deepEqual(items.map((entry) => entry.lane), ["waiting", "failed", "working", "done"]);
});

test("failed and waiting repositories outrank a very recent quiet repository", () => {
  const workItems = [item("waiting", "waiting"), item("failed", "failed")];
  const activity = Array.from({ length: 50 }, (_, index) => ({ repositoryId: "quiet", occurredAt: `2026-08-13T11:${String(index).padStart(2, "0")}:00Z` }));
  const ranked = rankRepositories(repositories, workItems, activity, generatedAt);
  assert.deepEqual(ranked.map((repo) => repo.id), ["failed", "waiting", "quiet"]);
});

test("heat includes recent activity volume and recency", () => {
  const repo = { id: "a", name: "a", updatedAt: "2026-08-13T11:00:00Z" };
  const cold = repositoryHeat(repo, [], [], generatedAt);
  const hot = repositoryHeat(repo, [], [{ repositoryId: "a", occurredAt: "2026-08-13T11:30:00Z" }, { repositoryId: "a", occurredAt: "2026-08-13T11:45:00Z" }], generatedAt);
  assert.ok(hot > cold);
});
