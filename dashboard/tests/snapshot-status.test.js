import test from "node:test";
import assert from "node:assert/strict";
import { classifySnapshot, STALE_AFTER_MS, CLOCK_SKEW_TOLERANCE_MS } from "../../docs/dashboard/snapshot-status.js";

const NOW = Date.parse("2026-08-13T03:00:00Z");

test("snapshot within the hourly refresh window is fresh", () => {
  const result = classifySnapshot(new Date(NOW - 60 * 60 * 1000).toISOString(), NOW);
  assert.equal(result.state, "fresh");
  assert.equal(result.label, "最新snapshot");
});

test("snapshot older than two hours is stale", () => {
  const result = classifySnapshot(new Date(NOW - STALE_AFTER_MS - 1).toISOString(), NOW);
  assert.equal(result.state, "stale");
  assert.equal(result.label, "古いsnapshot");
});

test("invalid generatedAt is never treated as fresh", () => {
  const result = classifySnapshot("not-a-date", NOW);
  assert.equal(result.state, "unknown");
  assert.equal(result.generated, null);
});

test("implausibly future generatedAt is never treated as fresh", () => {
  const result = classifySnapshot(new Date(NOW + CLOCK_SKEW_TOLERANCE_MS + 1).toISOString(), NOW);
  assert.equal(result.state, "unknown");
  assert.equal(result.label, "生成時刻異常");
});
