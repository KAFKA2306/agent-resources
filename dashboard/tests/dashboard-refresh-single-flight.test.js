import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../../docs/dashboard/dashboard.js", import.meta.url), "utf8");

function extractRefreshSource() {
  const start = source.indexOf("export async function refreshLiveState");
  const end = source.indexOf("async function loadDashboard", start);
  assert.notEqual(start, -1);
  assert.notEqual(end, -1);
  return source.slice(start, end).replace("export async function", "async function");
}

test("live refresh owns endpoint resolution inside the shared in-flight request", () => {
  const refresh = extractRefreshSource();
  const requestAssignment = refresh.indexOf("liveRequest = (async () => {");
  const endpointResolution = refresh.indexOf("await resolveLiveEndpoint()");

  assert.ok(requestAssignment >= 0, "refresh must assign the shared liveRequest");
  assert.ok(endpointResolution > requestAssignment, "endpoint resolution must happen inside the shared liveRequest");
  assert.match(refresh, /if \(liveRequest\) return liveRequest;/);
});

test("concurrent refreshes share one live fetch while endpoint resolution is pending", async () => {
  let releaseEndpoint;
  const endpointPending = new Promise((resolve) => {
    releaseEndpoint = () => resolve("https://example.test/api/dashboard-live");
  });
  let fetchCount = 0;

  const buildHarness = new Function(
    "resolveLiveEndpoint",
    "fetch",
    `${extractRefreshSource()}
    let baselineSnapshot = { generatedAt: "2026-08-20T00:00:00Z", repositories: [], workItems: [], activity: [] };
    let liveRequest = null;
    let liveRequestSequence = 0;
    let latestAppliedSequence = 0;
    let lastLiveSuccessAt = 0;
    const MIN_LIVE_SUCCESS_AGE_MS = 60 * 1000;
    const mergeLiveSnapshot = (_baseline, live) => live;
    const renderDashboard = () => {};
    const renderSnapshotMeta = () => {};
    const renderLiveMeta = () => {};
    const renderLiveFailure = () => {};
    return { refreshLiveState };`,
  );

  const { refreshLiveState } = buildHarness(
    () => endpointPending,
    async () => {
      fetchCount += 1;
      return {
        ok: true,
        async json() {
          return { fetchedAt: "2026-08-20T00:01:00Z", repositories: [], workItems: [], activity: [] };
        },
      };
    },
  );

  const first = refreshLiveState({ force: true });
  const second = refreshLiveState({ force: true });
  assert.equal(fetchCount, 0, "live fetch must wait for endpoint resolution");

  releaseEndpoint();
  await Promise.all([first, second]);
  assert.equal(fetchCount, 1, "concurrent refreshes must produce exactly one live request");
});

test("failed live refresh preserves the baseline and can be retried", async () => {
  let fetchCount = 0;

  const buildHarness = new Function(
    "fetch",
    `${extractRefreshSource()}
    const baselineSnapshot = {
      generatedAt: "2026-08-20T00:00:00Z",
      repositories: [{ id: "repo-1", name: "baseline" }],
      workItems: [],
      activity: [],
    };
    let liveRequest = null;
    let liveRequestSequence = 0;
    let latestAppliedSequence = 0;
    let lastLiveSuccessAt = 0;
    let dashboardRenderCount = 0;
    let fallbackCount = 0;
    const MIN_LIVE_SUCCESS_AGE_MS = 60 * 1000;
    const resolveLiveEndpoint = async () => "https://example.test/api/dashboard-live";
    const mergeLiveSnapshot = (_baseline, live) => live;
    const renderDashboard = () => { dashboardRenderCount += 1; };
    const renderSnapshotMeta = () => {};
    const renderLiveMeta = () => {};
    const renderLiveFailure = () => { fallbackCount += 1; };
    return {
      refreshLiveState,
      state: () => ({ baselineSnapshot, liveRequest, dashboardRenderCount, fallbackCount }),
    };`,
  );

  const { refreshLiveState, state } = buildHarness(async () => {
    fetchCount += 1;
    if (fetchCount === 1) throw new Error("network unavailable");
    return {
      ok: true,
      async json() {
        return { fetchedAt: "2026-08-20T00:02:00Z", repositories: [], workItems: [], activity: [] };
      },
    };
  });

  const failed = await refreshLiveState({ force: true });
  assert.equal(failed, null);
  assert.deepEqual(state().baselineSnapshot.repositories, [{ id: "repo-1", name: "baseline" }]);
  assert.equal(state().dashboardRenderCount, 0, "failure must not replace the already-rendered baseline");
  assert.equal(state().fallbackCount, 1, "failure must expose snapshot fallback state");
  assert.equal(state().liveRequest, null, "failed request must release the single-flight slot");

  const recovered = await refreshLiveState({ force: true });
  assert.notEqual(recovered, null, "a later refresh must be able to retry after failure");
  assert.equal(fetchCount, 2);
  assert.equal(state().dashboardRenderCount, 1);
  assert.equal(state().fallbackCount, 1);
});
