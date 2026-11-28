import test from "node:test";
import assert from "node:assert/strict";

import { createConditionalFetch } from "../../api/dashboard-live.js";

function githubHeaders(etag, remaining = 4999) {
  return {
    "content-type": "application/json",
    etag,
    "x-ratelimit-resource": "core",
    "x-ratelimit-limit": "5000",
    "x-ratelimit-remaining": String(remaining),
    "x-ratelimit-reset": "1900000000",
  };
}

test("conditional live fetch reuses cached JSON after an authenticated 304", async () => {
  const cache = new Map();
  const stats = { conditionalRequestCount: 0, notModifiedRequestCount: 0 };
  const seen = [];
  let requestNumber = 0;

  const upstream = async (url, options) => {
    requestNumber += 1;
    seen.push({
      url: String(url),
      authorization: options.headers.get("Authorization"),
      ifNoneMatch: options.headers.get("If-None-Match"),
    });
    if (requestNumber === 1) {
      return new Response(JSON.stringify({ workflow_runs: [{ id: 101 }] }), {
        status: 200,
        headers: githubHeaders('"workflow-v1"'),
      });
    }
    return new Response(null, {
      status: 304,
      headers: githubHeaders('"workflow-v1"'),
    });
  };

  const fetchImpl = createConditionalFetch(upstream, cache, stats);
  const options = { headers: { Authorization: "Bearer test-token" } };
  const url = "https://api.github.com/repos/KAFKA2306/alpha/actions/runs?per_page=1";

  const first = await fetchImpl(url, options);
  assert.equal(first.status, 200);
  assert.deepEqual(await first.json(), { workflow_runs: [{ id: 101 }] });

  const second = await fetchImpl(url, options);
  assert.equal(second.status, 200);
  assert.deepEqual(await second.json(), { workflow_runs: [{ id: 101 }] });

  assert.equal(seen[0].authorization, "Bearer test-token");
  assert.equal(seen[0].ifNoneMatch, null);
  assert.equal(seen[1].authorization, "Bearer test-token");
  assert.equal(seen[1].ifNoneMatch, '"workflow-v1"');
  assert.equal(stats.conditionalRequestCount, 1);
  assert.equal(stats.notModifiedRequestCount, 1);
  assert.equal(cache.size, 1);
});
