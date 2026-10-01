const REPOSITORY = "KAFKA2306/agent-resources";
const API_BASE = `https://api.github.com/repos/${REPOSITORY}`;

const freshness = document.querySelector("#factory-freshness");
const mainSha = document.querySelector("#factory-main-sha");
const pagesRun = document.querySelector("#factory-pages-run");
const observer = document.querySelector("#factory-observer");
const canonicalIssue = document.querySelector("#factory-canonical-issue");
const activePullRequests = document.querySelector("#factory-active-prs");
const capabilities = document.querySelector("#factory-capabilities");

const CAPABILITY_PRESENTATION = {
  "observe-classify": {
    code: "A01",
    name: "SENTINEL ARRAY",
    description: "異常を発見し、原因の型を見抜いて次の行動へ振り分ける。",
  },
  "bounded-retry": {
    code: "A02",
    name: "RESILIENCE LOOP",
    description: "失敗を無限ループさせず、許可された回数だけ自動再試行する。",
  },
  "deterministic-repair": {
    code: "A03",
    name: "REPAIR CORE",
    description: "既知の壊れ方を検知すると、決められた修復手順を即座に投入する。",
  },
  "autonomous-merge": {
    code: "A04",
    name: "MERGE AUTOPILOT",
    description: "CI・repository rules・安全条件を満たした変更をmainへ自律統合する。",
  },
  "deploy-production-probe": {
    code: "A05",
    name: "PRODUCTION SENTINEL",
    description: "deploy後の本番を直接観測し、期待したrevisionが生きているか確認する。",
  },
  "production-fix-forward": {
    code: "A06",
    name: "RECOVERY DRIVE",
    description: "本番異常を検知したあと、停止ではなく安全な前進修復へ移る。",
  },
  "pages-current-evidence": {
    code: "A07",
    name: "EVIDENCE STREAM",
    description: "current mainの証拠を公開Control Towerまで連続同期する。",
  },
  "pages-freshness-gate": {
    code: "A08",
    name: "FRESHNESS SHIELD",
    description: "古い公開状態を弾き、current mainと一致した情報だけを通す。",
  },
  "general-diagnosis-patch": {
    code: "A09",
    name: "DIAGNOSTIC ENGINE",
    description: "未知の障害を解析し、一般化された修正ルートへ接続する。",
  },
  "provider-runner-recovery": {
    code: "A10",
    name: "FAILOVER MATRIX",
    description: "runnerやprovider障害時に実行経路を切り替え、作業継続を狙う。",
  },
};

const CAPABILITY_STATE = {
  VERIFIED: { label: "VERIFIED LIVE", tone: "verified" },
  EXISTING: { label: "ONLINE", tone: "online" },
  DISCONNECTED: { label: "DEGRADED", tone: "degraded" },
  MISSING: { label: "OFFLINE", tone: "offline" },
  UNVERIFIED: { label: "CHECKING", tone: "checking" },
};

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
  const list = Array.isArray(items) ? items : [];
  const onlineCount = list.filter((item) => ["VERIFIED", "EXISTING"].includes(item?.state)).length;

  const summary = document.createElement("div");
  summary.className = "autonomy-summary";
  const summaryCopy = document.createElement("div");
  summaryCopy.className = "autonomy-summary-copy";
  const summaryKicker = document.createElement("span");
  summaryKicker.textContent = "AUTONOMOUS SYSTEMS ONLINE";
  const summaryValue = document.createElement("strong");
  summaryValue.textContent = `${onlineCount} / ${list.length}`;
  summaryCopy.append(summaryKicker, summaryValue);

  const rail = document.createElement("div");
  rail.className = "autonomy-rail";
  const fill = document.createElement("span");
  fill.style.width = list.length ? `${Math.round((onlineCount / list.length) * 100)}%` : "0%";
  rail.append(fill);
  summary.append(summaryCopy, rail);
  capabilities.append(summary);

  for (const item of list) {
    const presentation = CAPABILITY_PRESENTATION[item.id] || {
      code: "SYS",
      name: item.label || item.id || "Capability",
      description: "Factory capability.",
    };
    const statePresentation = CAPABILITY_STATE[item.state] || CAPABILITY_STATE.UNVERIFIED;

    const card = document.createElement("article");
    card.className = "capability-module";
    card.dataset.capabilityState = item.state || "UNVERIFIED";
    card.dataset.capabilityTone = statePresentation.tone;

    const header = document.createElement("header");
    header.className = "capability-module-header";

    const code = document.createElement("span");
    code.className = "capability-code";
    code.textContent = presentation.code;

    const state = document.createElement("span");
    state.className = "capability-state";
    state.textContent = statePresentation.label;

    header.append(code, state);

    const heading = document.createElement("strong");
    heading.className = "capability-name";
    heading.textContent = presentation.name;

    const description = document.createElement("p");
    description.className = "capability-description";
    description.textContent = presentation.description;

    const pulse = document.createElement("span");
    pulse.className = "capability-pulse";
    pulse.setAttribute("aria-hidden", "true");

    card.append(header, heading, description, pulse);
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
