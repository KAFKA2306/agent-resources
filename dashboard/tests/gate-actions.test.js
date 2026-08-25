import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const dashboardSource = await readFile(new URL("../../docs/dashboard/gate-actions.js", import.meta.url), "utf8");
const dashboardHtml = await readFile(new URL("../../docs/dashboard/index.html", import.meta.url), "utf8");

test("state gate detail identifies owner repository and canonical action", () => {
  assert.match(dashboardSource, /Owner repository:/);
  assert.match(dashboardSource, /対応先を開く/);
  assert.match(dashboardSource, /action\.href = canonicalLink\.href/);
});

test("dashboard loads the gate action enhancement", () => {
  assert.match(dashboardHtml, /gate-actions\.js/);
});
