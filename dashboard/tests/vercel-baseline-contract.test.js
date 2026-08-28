import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const config = JSON.parse(
  fs.readFileSync(new URL("../../vercel.json", import.meta.url), "utf8"),
);

test("Vercel serves the canonical dashboard baseline before applying live state", () => {
  const dashboardRewrite = config.rewrites?.find(
    (rewrite) => rewrite.source === "/dashboard/dashboard.json",
  );

  assert.ok(dashboardRewrite, "dashboard baseline rewrite must exist");
  assert.equal(
    dashboardRewrite.destination,
    "https://kafka2306.github.io/agent-resources/dashboard/dashboard.json",
  );
  assert.notEqual(dashboardRewrite.destination, "/api/dashboard-live");
});

test("Vercel keeps the live endpoint separate from the baseline", () => {
  assert.ok(config.functions?.["api/dashboard-live.js"], "live endpoint must remain deployed");
});
