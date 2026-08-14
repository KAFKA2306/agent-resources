import test from "node:test";
import assert from "node:assert/strict";

import { LIVE_MAX_AGE_MS, classifyLive, mergeLiveSnapshot } from "../../docs/dashboard/live-overlay.js";

test("live freshness is explicit and bounded", () => {
  const now = Date.parse("2026-08-14T05:30:00Z");
  assert.equal(classifyLive("2026-08-14T05:29:00Z", now).label, "LIVE");
  assert.equal(classifyLive(new Date(now - LIVE_MAX_AGE_MS - 1).toISOString(), now).label, "STALE");
  assert.equal(classifyLive("not-a-date", now).label, "SNAPSHOT FALLBACK");
});

test("live overlay replaces volatile state but preserves heavy baseline stats", () => {
  const baseline = {
    generatedAt: "2026-08-14T04:00:00Z",
    stats: { scope: "public", monthly: [{ month: "2026-08" }] },
    repositories: [{ id: "old", visibility: "public" }],
    workItems: [],
    activity: [],
  };
  const live = {
    schemaVersion: "1.0.0",
    scope: "public",
    fetchedAt: "2026-08-14T05:30:00Z",
    repositories: [{ id: "repo", visibility: "public", archived: false }],
    workItems: [{ id: "item", repositoryId: "repo" }],
    activity: [{ id: "activity", repositoryId: "repo" }],
    requestBudget: { requestCount: 1 },
  };
  const merged = mergeLiveSnapshot(baseline, live);
  assert.equal(merged.repositories[0].id, "repo");
  assert.equal(merged.stats, baseline.stats);
  assert.equal(merged.liveFetchedAt, live.fetchedAt);
});

test("live overlay rejects private or dangling data", () => {
  const baseline = { repositories: [], workItems: [], activity: [] };
  assert.throws(() => mergeLiveSnapshot(baseline, {
    scope: "public",
    fetchedAt: "2026-08-14T05:30:00Z",
    repositories: [{ id: "private", visibility: "private", archived: false }],
    workItems: [],
    activity: [],
  }), /public repository boundary/);
  assert.throws(() => mergeLiveSnapshot(baseline, {
    scope: "public",
    fetchedAt: "2026-08-14T05:30:00Z",
    repositories: [{ id: "public", visibility: "public", archived: false }],
    workItems: [{ repositoryId: "missing" }],
    activity: [],
  }), /non-public repository/);
});
