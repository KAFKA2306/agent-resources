import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const dashboardSource = await readFile(new URL("../../docs/dashboard/gate-actions.js", import.meta.url), "utf8");
const dashboardHtml = await readFile(new URL("../../docs/dashboard/index.html", import.meta.url), "utf8");

test("state gate detail identifies owner repository and canonical action", () => {
  assert.match(dashboardSource, /Owner repository:/);
  assert.match(dashboardSource, /次の行動: 対応先を開く/);
  assert.match(dashboardSource, /action\.href = canonicalLink\.href/);
});

test("highest priority human action is promoted before the gate summary", () => {
  assert.match(dashboardSource, /primary\.id = "primary-action"/);
  assert.match(dashboardSource, /最優先の対応/);
  assert.match(dashboardSource, /data-lane=\\"waiting\\"/);
  assert.match(dashboardSource, /data-lane=\\"failed\\"/);
  assert.match(dashboardSource, /selected\.click\(\)/);
  assert.match(dashboardSource, /insertBefore\(primary, operationsSummary\)/);
});

test("dashboard loads the gate action enhancement", () => {
  assert.match(dashboardHtml, /gate-actions\.js/);
});
