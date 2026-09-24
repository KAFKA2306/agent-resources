const REPOSITORY = "KAFKA2306/agent-resources";
const API_BASE = `https://api.github.com/repos/${REPOSITORY}`;

const freshness = document.querySelector("#factory-freshness");
const mainSha = document.querySelector("#factory-main-sha");
const pagesRun = document.querySelector("#factory-pages-run");
const observer = document.querySelector("#factory-observer");
const canonicalIssue = document.querySelector("#factory-canonical-issue");
const activePullRequests = document.querySelector("#factory-active-prs");
const capabilities = document.querySelector("#factory-capabilities");

function shortSha(value) {
  return typeof value === "string" && value.length >= 7 ? value.slice(0, 12) : "unknown";
}

function setFreshness(label, state) {
  freshness.textContent = label;
  freshness.dataset.state = state;
}

function replaceWithLink(root, label, url) {
  root.replaceChildren();
  if (!url) {
    root.textContent = label;
    return;
  }
  const link = document.createElement("a");
  link.className = "world-station-link";
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  const strong = document.createElement("strong");
  strong.textContent = label;
  link.append(strong);
  root.append(link);
}

function renderCapabilities(items) {
  capabilities.replaceChildren();
  for (const item of Array.isArray(items) ? items : []) {
    const card = document.createElement("div");
    card.className = "world-station";
    card.dataset.capabilityState = item.state || "UNVERIFIED";

    const heading = document.createElement("strong");
    heading.textContent = item.label || item.id || "Capability";
    const state = document.createElement("small");
    state.className = "muted";
    state.textContent = item.state || "UNVERIFIED";

    card.append(heading, state);
    capabilities.append(card);
  }
}

function renderPullRequests(items) {
  activePullRequests.replaceChildren();
  const pulls = Array.isArray(items) ? items : [];
  if (pulls.length === 0) {
    activePullRequests.textContent = "0 open";
    return;
  }
  const list = document.createElement("div");
  list.className = "world-work-items";
  for (const item of pulls) {
    const link = document.createElement("a");
    link.className = "world-agent";
    link.dataset.lane = "working";
    link.href = item.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";

    const badge = document.createElement("span");
    badge.className = "agent-badge";
    badge.textContent = `#${item.number}`;
    const copy = document.createElement("span");
    copy.className = "world-agent-copy";
    const title = document.createElement("strong");
    title.textContent = item.title;
    const detail = document.createElement("small");
    detail.textContent = `${shortSha(item.headSha)}${item.draft ? " · draft" : ""}`;
    copy.append(title, detail);
    link.append(badge, copy);
    list.append(link);
  }
  activePullRequests.append(list);
}

function renderStaticState(payload) {
  const sourceRevision = payload?.sourceRevision;
  mainSha.textContent = shortSha(sourceRevision);
  mainSha.title = sourceRevision || "";

  const runId = payload?.pages?.workflowRunId;
  replaceWithLink(
    pagesRun,
    runId ? `Build / deploy run #${runId}` : "Build / deploy run unknown",
    payload?.pages?.workflowRunUrl,
  );

  const observerState = payload?.observer?.state || "UNVERIFIED";
  const observerRun = payload?.observer?.runId;
  replaceWithLink(
    observer,
    observerRun ? `${observerState} · run #${observerRun}` : observerState,
    payload?.observer?.url,
  );

  const issue = payload?.canonicalIssue;
  replaceWithLink(
    canonicalIssue,
    issue ? `#${issue.number} · ${issue.state}` : "UNVERIFIED",
    issue?.url,
  );

  renderPullRequests(payload?.activePullRequests);
  renderCapabilities(payload?.capabilities);
}

async function fetchJson(url) {
  const response = await fetch(url, {
    cache: "no-store",
    headers: { Accept: "application/vnd.github+json" },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

async function verifyProductionFreshness(payload) {
  const sourceRevision = payload?.sourceRevision;
  const runId = payload?.pages?.workflowRunId;
  if (!sourceRevision || !runId) {
    setFreshness("UNVERIFIED · provenance missing", "unknown");
    return;
  }

  try {
    const [liveMain, run] = await Promise.all([
      fetchJson(`${API_BASE}/commits/main`),
      fetchJson(`${API_BASE}/actions/runs/${encodeURIComponent(runId)}`),
    ]);

    if (liveMain?.sha !== sourceRevision) {
      setFreshness(
        `FAIL · stale ${shortSha(sourceRevision)} ≠ main ${shortSha(liveMain?.sha)}`,
        "failed",
      );
      return;
    }

    if (run?.status === "completed" && run?.conclusion === "success") {
      setFreshness(`VERIFIED · main ${shortSha(sourceRevision)}`, "fresh");
      return;
    }

    if (run?.status === "completed") {
      setFreshness(`FAIL · deploy ${run?.conclusion || "unknown"}`, "failed");
      return;
    }

    setFreshness(`CURRENT · deploy ${run?.status || "verifying"}`, "stale");
  } catch (error) {
    setFreshness("UNVERIFIED · live GitHub read-back failed", "unknown");
    console.error("factory evidence live verification failed", error);
  }
}

async function loadFactoryEvidence() {
  try {
    const payload = await fetchJson("./factory-state.json");
    renderStaticState(payload);
    await verifyProductionFreshness(payload);
  } catch (error) {
    setFreshness("UNVERIFIED · factory-state unavailable", "failed");
    console.error("factory evidence snapshot failed", error);
  }
}

loadFactoryEvidence();
