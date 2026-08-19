import test from "node:test";
import assert from "node:assert/strict";

import { LIVE_MAX_AGE_MS, classifyLive, mergeLiveSnapshot } from "../../docs/dashboard/live-overlay.js";

test("live freshness is explicit and bounded", () => {
  const now = Date.parse("2026-08-14T05:30:00Z");
  const fresh = classifyLive("2026-08-14T05:29:00Z", now);
  const stale = classifyLive(new Date(now - LIVE_MAX_AGE_MS - 1).toISOString(), now);
  const failed = classifyLive("not-a-date", now);
  assert.deepEqual({ label: fresh.label, state: fresh.state }, { label: "LIVE", state: "fresh" });
  assert.deepEqual({ label: stale.label, state: stale.state }, { label: "STALE", state: "stale" });
  assert.deepEqual(
    { label: failed.label, state: failed.state },
    { label: "SNAPSHOT FALLBACK", state: "failed" },
  );
});

test("live overlay replaces volatile state but preserves heavy baseline stats and public links", () => {
  const baseline = {
    generatedAt: "2026-08-14T04:00:00Z",
    stats: { scope: "public", monthly: [{ month: "2026-08" }] },
    repositories: [{
      id: "repo",
      visibility: "public",
      publicLinks: [{ kind: "pages", url: "https://kafka2306.github.io/repo/" }],
    }],
    workItems: [],
    activity: [],
  };
  const live = {
    schemaVersion: "1.0.0",
    scope: "public",
    fetchedAt: "2026-08-14T05:30:00Z",
    repositories: [{ id: "repo", visibility: "public", archived: false, updatedAt: "2026-08-14T05:29:00Z" }],
    workItems: [{ id: "item", repositoryId: "repo" }],
    activity: [{ id: "activity", repositoryId: "repo" }],
    requestBudget: { requestCount: 1 },
  };
  const merged = mergeLiveSnapshot(baseline, live);
  assert.equal(merged.repositories[0].id, "repo");
  assert.equal(merged.repositories[0].updatedAt, "2026-08-14T05:29:00Z");
  assert.deepEqual(merged.repositories[0].publicLinks, baseline.repositories[0].publicLinks);
  assert.equal(merged.stats, baseline.stats);
  assert.equal(merged.liveFetchedAt, live.fetchedAt);
});

test("live-only repositories remain visible without invented public links", () => {
  const merged = mergeLiveSnapshot(
    { repositories: [], workItems: [], activity: [] },
    {
      scope: "public",
      fetchedAt: "2026-08-14T05:30:00Z",
      repositories: [{ id: "new", visibility: "public", archived: false }],
      workItems: [],
      activity: [],
    },
  );
  assert.equal(merged.repositories[0].id, "new");
  assert.equal(Object.hasOwn(merged.repositories[0], "publicLinks"), false);
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
