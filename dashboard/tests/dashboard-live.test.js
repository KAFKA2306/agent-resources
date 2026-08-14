import test from "node:test";
import assert from "node:assert/strict";

import {
  LIVE_CACHE_SECONDS,
  LiveDataError,
  classifyLane,
  collectLiveState,
  inferGroup,
  normalizeRepository,
  workflowState,
} from "../live-core.js";

function headers(values = {}) {
  const normalized = new Map(Object.entries(values).map(([key, value]) => [key.toLowerCase(), String(value)]));
  return { get: (key) => normalized.get(String(key).toLowerCase()) ?? null };
}

function response(payload, { status = 200, resource = "core", remaining = 4999 } = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: headers({
      "x-ratelimit-resource": resource,
      "x-ratelimit-limit": resource === "search" ? 30 : 5000,
      "x-ratelimit-remaining": remaining,
      "x-ratelimit-reset": 1900000000,
    }),
    async json() { return payload; },
  };
}

function repository(name, nodeId, extra = {}) {
  return {
    node_id: nodeId,
    name,
    owner: { login: "KAFKA2306" },
    html_url: `https://github.com/KAFKA2306/${name}`,
    visibility: "public",
    private: false,
    archived: false,
    updated_at: "2026-08-14T05:00:00Z",
    pushed_at: "2026-08-14T04:59:00Z",
    topics: ["agent-zone-automation"],
    ...extra,
  };
}

function searchItem(repo, number, extra = {}) {
  return {
    number,
    title: `Item ${number}`,
    state: "open",
    html_url: `https://github.com/KAFKA2306/${repo}/issues/${number}`,
    repository_url: `https://api.github.com/repos/KAFKA2306/${repo}`,
    updated_at: "2026-08-14T05:20:00Z",
    ...extra,
  };
}

test("repository normalization remains public-only and topic-driven", () => {
  assert.equal(inferGroup(repository("alpha", "R1")), "automation");
  assert.equal(normalizeRepository(repository("private", "R2", { private: true, visibility: "private" })), null);
  assert.equal(normalizeRepository(repository("archived", "R3", { archived: true })), null);
  assert.equal(normalizeRepository(repository("other", "R4", { owner: { login: "someone" } })), null);
});

test("lane and workflow state contracts match canonical dashboard", () => {
  assert.deepEqual(classifyLane({ kind: "issue", state: "open" }), { lane: "working", laneReason: "open_issue" });
  assert.deepEqual(classifyLane({ kind: "pull_request", state: "open" }), { lane: "waiting", laneReason: "open_pull_request" });
  assert.equal(workflowState({ status: "completed", conclusion: "success" }), "completed");
  assert.equal(workflowState({ status: "completed", conclusion: "failure" }), "failed");
  assert.equal(workflowState({ status: "in_progress", conclusion: null }), "in_progress");
});

test("live collector aggregates repositories, open work, latest workflows, and activity within a bounded request budget", async () => {
  const calls = [];
  const fetchImpl = async (url) => {
    calls.push(url);
    const parsed = new URL(url);
    if (parsed.pathname === "/users/KAFKA2306/repos") {
      return response([repository("alpha", "R_alpha"), repository("beta", "R_beta")]);
    }
    if (parsed.pathname === "/search/issues") {
      const query = parsed.searchParams.get("q");
      if (query.includes("is:open")) {
        return response({ total_count: 2, items: [
          searchItem("alpha", 7),
          searchItem("beta", 9, { pull_request: { url: "https://api.github.com/pulls/9" }, html_url: "https://github.com/KAFKA2306/beta/pull/9" }),
        ] }, { resource: "search", remaining: 29 });
      }
      return response({ total_count: 1, items: [searchItem("alpha", 7)] }, { resource: "search", remaining: 28 });
    }
    if (parsed.pathname.endsWith("/alpha/actions/runs")) {
      return response({ workflow_runs: [{
        id: 101,
        run_number: 11,
        name: "CI",
        status: "completed",
        conclusion: "success",
        html_url: "https://github.com/KAFKA2306/alpha/actions/runs/101",
        updated_at: "2026-08-14T05:25:00Z",
      }] });
    }
    if (parsed.pathname.endsWith("/beta/actions/runs")) return response({ workflow_runs: [] });
    throw new Error(`unexpected URL ${url}`);
  };

  const live = await collectLiveState({ token: "test-token", fetchImpl, now: new Date("2026-08-14T05:30:00Z") });
  assert.equal(live.scope, "public");
  assert.equal(live.repositories.length, 2);
  assert.equal(live.workItems.length, 3);
  assert.equal(live.workItems.filter((item) => item.kind === "workflow_run").length, 1);
  assert.equal(live.activity.some((item) => item.kind === "workflow_run"), true);
  assert.equal(live.requestBudget.requestCount, 5);
  assert.equal(live.requestBudget.workflowRequestCount, 2);
  assert.equal(live.requestBudget.theoreticalRequestsPerHourAtMaxAge, Math.ceil(3600 / LIVE_CACHE_SECONDS) * 5);
  assert.equal(calls.length, 5);
  assert.equal(live.rateLimits.search.remaining, 28);
});

test("missing server credential fails closed", async () => {
  await assert.rejects(() => collectLiveState({ fetchImpl: async () => response([]) }), (error) => {
    assert.equal(error instanceof LiveDataError, true);
    assert.equal(error.code, "missing_server_credential");
    return true;
  });
});

test("rate limit errors are explicit and do not produce partial live truth", async () => {
  const fetchImpl = async () => response({ message: "rate limited" }, { status: 403, remaining: 0 });
  await assert.rejects(() => collectLiveState({ token: "test-token", fetchImpl }), (error) => {
    assert.equal(error.code, "github_rate_limited");
    assert.equal(error.details.status, 403);
    return true;
  });
});
