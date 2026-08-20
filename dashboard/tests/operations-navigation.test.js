import test from "node:test";
import assert from "node:assert/strict";
import { laneFromUrl, urlWithLane } from "../../docs/dashboard/operations-navigation.js";

test("reads supported operations lane from URL", () => {
  assert.equal(laneFromUrl("https://example.com/dashboard/?lane=waiting"), "waiting");
  assert.equal(laneFromUrl("https://example.com/dashboard/?lane=failed"), "failed");
  assert.equal(laneFromUrl("https://example.com/dashboard/?lane=done"), "done");
});

test("rejects unsupported lane values", () => {
  assert.equal(laneFromUrl("https://example.com/dashboard/?lane=working"), null);
  assert.equal(laneFromUrl("https://example.com/dashboard/?lane=unknown"), null);
});

test("updates lane without dropping unrelated URL state", () => {
  const result = urlWithLane("https://example.com/dashboard/?repo=agent-resources#activity", "failed");
  assert.equal(result.pathname, "/dashboard/");
  assert.equal(result.searchParams.get("repo"), "agent-resources");
  assert.equal(result.searchParams.get("lane"), "failed");
  assert.equal(result.hash, "#activity");
});

test("removes lane when no supported lane is selected", () => {
  const result = urlWithLane("https://example.com/dashboard/?lane=waiting&repo=agent-resources", null);
  assert.equal(result.searchParams.has("lane"), false);
  assert.equal(result.searchParams.get("repo"), "agent-resources");
});
