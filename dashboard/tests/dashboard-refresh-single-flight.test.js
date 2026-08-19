import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../../docs/dashboard/dashboard.js", import.meta.url), "utf8");

test("live refresh owns endpoint resolution inside the shared in-flight request", () => {
  const start = source.indexOf("export async function refreshLiveState");
  const end = source.indexOf("async function loadDashboard", start);
  assert.notEqual(start, -1);
  assert.notEqual(end, -1);

  const refresh = source.slice(start, end);
  const requestAssignment = refresh.indexOf("liveRequest = (async () => {");
  const endpointResolution = refresh.indexOf("await resolveLiveEndpoint()");

  assert.ok(requestAssignment >= 0, "refresh must assign the shared liveRequest");
  assert.ok(endpointResolution > requestAssignment, "endpoint resolution must happen inside the shared liveRequest");
  assert.match(refresh, /if \(liveRequest\) return liveRequest;/);
});
