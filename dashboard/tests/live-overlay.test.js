import test from "node:test";
import assert from "node:assert/strict";

import { classifyLive, mergeLiveSnapshot } from "../../docs/dashboard/live-overlay.js";

test("live freshness follows the declared API cache policy", () => {
  const now = Date.parse("2026-08-14T05:30:00Z");
  const maxAgeSeconds = 600;
  const fresh = classifyLive("2026-08-14T05:20:01Z", maxAgeSeconds, now);
  const stale = classifyLive("2026-08-14T05:19:59Z", maxAgeSeconds, now);
  const failedTimestamp = classifyLive("not-a-date", maxAgeSeconds, now);
  const missingPolicy = classifyLive("2026-08-14T05:29:00Z", undefined, now);
  assert.deepEqual({ label: fresh.label, state: fresh.state }, { label: "LIVE", state: "fresh" });
  assert.deepEqual({ label: stale.label, state: stale.state }, { label: "STALE", state: "stale" });
  assert.equal(fresh.fetched.toISOString(), "2026-08-14T05:20:01.000Z");
  assert.deepEqual(
    { label: failedTimestamp.label, state: failedTimestamp.state },
    { label: "SNAPSHOT FALLBACK", state: "failed" },
  );
  assert.deepEqual(
    { label: missingPolicy.label, state: missingPolicy.state },
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
    workItems: [{ id: "item", repositoryId: "repo", kind: "issue", number: 1 }],
    activity: [{ id: "activity", repositoryId: "repo", kind: "issue", occurredAt: "2026-08-14T05:29:00Z" }],
    requestBudget: { requestCount: 1 },
  };
  const merged = mergeLiveSnapshot(baseline, live);
  assert.equal(merged.repositories[0].id, "repo");
  assert.equal(merged.repositories[0].updatedAt, "2026-08-14T05:29:00Z");
  assert.deepEqual(merged.repositories[0].publicLinks, baseline.repositories[0].publicLinks);
  assert.equal(merged.stats, baseline.stats);
  assert.equal(merged.liveFetchedAt, live.fetchedAt);
  assert.equal(merged.workItems.length, 1);
  assert.equal(merged.activity.length, 1);
});

test("live overlay keeps workflow evidence from the canonical snapshot while refreshing issue and PR state", () => {
  const baseline = {
    generatedAt: "2026-08-14T04:00:00Z",
    repositories: [{ id: "repo", visibility: "public" }],
    workItems: [
      { id: "old-issue", repositoryId: "repo", kind: "issue", number: 1, state: "open" },
      { id: "workflow", repositoryId: "repo", kind: "workflow_run", number: 20, state: "failed" },
    ],
    activity: [
      { id: "activity:old-issue", repositoryId: "repo", kind: "issue", occurredAt: "2026-08-14T03:00:00Z" },
      { id: "activity:workflow", repositoryId: "repo", kind: "workflow_run", occurredAt: "2026-08-14T03:30:00Z" },
    ],
  };
  const live = {
    scope: "public",
    fetchedAt: "2026-08-14T05:30:00Z",
    repositories: [{ id: "repo", visibility: "public", archived: false }],
    workItems: [{ id: "new-issue", repositoryId: "repo", kind: "issue", number: 2, state: "open" }],
    activity: [{ id: "activity:new-issue", repositoryId: "repo", kind: "issue", occurredAt: "2026-08-14T05:00:00Z" }],
  };

  const merged = mergeLiveSnapshot(baseline, live);
  assert.deepEqual(merged.workItems.map((item) => item.id), ["new-issue", "workflow"]);
  assert.deepEqual(merged.activity.map((item) => item.id), ["activity:new-issue", "activity:workflow"]);
  assert.equal(merged.summary.workItemCount, 2);
  assert.equal(merged.summary.activityCount, 2);
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
