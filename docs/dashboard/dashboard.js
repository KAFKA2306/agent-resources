const assetVersion = encodeURIComponent(new URL(import.meta.url).searchParams.get("v") || Date.now().toString());
const [
  { compareWorkItems },
  { classifySnapshot },
  { classifyLive, mergeLiveSnapshot },
  { renderStats },
  { createPublicSurfaceLinks, renderWorld },
] = await Promise.all([
  import(`./ranking.js?v=${assetVersion}`),
  import(`./snapshot-status.js?v=${assetVersion}`),
  import(`./live-overlay.js?v=${assetVersion}`),
  import(`./stats.js?v=${assetVersion}`),
  import(`./world.js?v=${assetVersion}`),
]);

const repositoryCount = document.querySelector("#repository-count");
const snapshotStatus = document.querySelector("#snapshot-status");
const snapshotGeneratedAt = document.querySelector("#snapshot-generated-at");
const liveFetchedAt = document.querySelector("#live-fetched-at");
const workspaceMessage = document.querySelector("#workspace-message");
const laneGates = document.querySelector("#lane-gates");
const gateDetail = document.querySelector("#gate-detail");
const activityFeed = document.querySelector("#activity-feed");

const ACTIVITY_LABELS = { issue: "Issue", pull_request: "Pull Request", workflow_run: "Workflow Run" };
const GATES = [
  { lane: "waiting", label: "判断待ち" },
  { lane: "failed", label: "失敗・要確認" },
  { lane: "done", label: "完了報告" },
];
const LIVE_CONFIG_URL = "./live-config.json";
const MIN_LIVE_SUCCESS_AGE_MS = 60 * 1000;

let baselineSnapshot = null;
let liveEndpoint = null;
let liveEndpointResolved = false;
let liveRequest = null;
let liveRequestSequence = 0;
let latestAppliedSequence = 0;
let lastLiveSuccessAt = 0;

function showGateItems(label, items, repositoriesById) {
  gateDetail.replaceChildren();
  gateDetail.hidden = false;
  const heading = document.createElement("h3");
  heading.textContent = `${label} (${items.length})`;
  gateDetail.append(heading);
  if (items.length === 0) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "対象は0件です。";
    gateDetail.append(empty);
    return;
  }
  const list = document.createElement("div");
  list.className = "gate-item-list";
  for (const item of items.slice().sort(compareWorkItems)) {
    const row = document.createElement("div");
    const link = document.createElement("a");
    link.href = item.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    const repo = repositoriesById.get(item.repositoryId);
    link.textContent = `${repo ? repo.name : "unknown"} · ${item.title}`;
    row.append(link);
    const publicSurfaceLinks = repo ? createPublicSurfaceLinks(repo) : null;
    if (publicSurfaceLinks) row.append(publicSurfaceLinks);
    list.append(row);
  }
  gateDetail.append(list);
}

function renderGates(workItems, repositoriesById) {
  laneGates.replaceChildren();
  for (const gate of GATES) {
    const items = workItems.filter((item) => item.lane === gate.lane);
    const button = document.createElement("button");
    button.className = "lane-gate";
    button.dataset.lane = gate.lane;
    button.type = "button";
    button.innerHTML = `<span>${gate.label}</span><strong>${items.length}</strong>`;
    button.addEventListener("click", () => showGateItems(gate.label, items, repositoriesById));
    laneGates.append(button);
  }
}

function formatActivityTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ja-JP", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(date);
}

function formatSnapshotTime(date) {
  return new Intl.DateTimeFormat("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function renderSnapshotMeta(snapshot) {
  const freshness = classifySnapshot(snapshot.generatedAt);
  if (!freshness.generated) {
    snapshotGeneratedAt.removeAttribute("datetime");
    snapshotGeneratedAt.textContent = "Snapshot: 不明";
  } else {
    snapshotGeneratedAt.dateTime = freshness.generated.toISOString();
    snapshotGeneratedAt.textContent = `Snapshot: ${formatSnapshotTime(freshness.generated)}`;
  }
  if (snapshotStatus.dataset.state === "loading") {
    snapshotStatus.dataset.state = freshness.state;
    snapshotStatus.textContent = freshness.label;
  }
}

function renderLiveMeta(fetchedAt) {
  const freshness = classifyLive(fetchedAt);
  snapshotStatus.dataset.state = freshness.state;
  snapshotStatus.textContent = freshness.label;
  if (!freshness.fetched) {
    liveFetchedAt.removeAttribute("datetime");
    liveFetchedAt.textContent = "Live: 取得できません";
    return;
  }
  liveFetchedAt.dateTime = freshness.fetched.toISOString();
  liveFetchedAt.textContent = `Live: ${formatSnapshotTime(freshness.fetched)}`;
}

function renderLiveFailure(message = "Live取得失敗") {
  snapshotStatus.dataset.state = "failed";
  snapshotStatus.textContent = "SNAPSHOT FALLBACK";
  liveFetchedAt.removeAttribute("datetime");
  liveFetchedAt.textContent = `Live: ${message}`;
}

function renderActivity(activity, repositoriesById) {
  activityFeed.replaceChildren();
  const items = activity
    .filter((item) => ACTIVITY_LABELS[item.kind])
    .slice()
    .sort((a, b) => b.occurredAt.localeCompare(a.occurredAt));
  if (items.length === 0) {
    const empty = document.createElement("p");
    empty.className = "muted activity-empty";
    empty.textContent = "直近7日の活動は0件です。";
    activityFeed.append(empty);
    return;
  }
  for (const item of items) {
    const link = document.createElement("a");
    link.className = "activity-item";
    link.href = item.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    const meta = document.createElement("span");
    meta.className = "activity-meta";
    const kind = document.createElement("span");
    kind.className = "activity-kind";
    kind.textContent = ACTIVITY_LABELS[item.kind];
    const time = document.createElement("time");
    time.dateTime = item.occurredAt;
    time.textContent = formatActivityTime(item.occurredAt);
    meta.append(kind, time);
    const summary = document.createElement("strong");
    summary.textContent = item.summary || ACTIVITY_LABELS[item.kind];
    const repo = document.createElement("small");
    repo.textContent = repositoriesById.get(item.repositoryId)?.name || "unknown";
    link.append(meta, summary, repo);
    activityFeed.append(link);
  }
}

function renderDashboard(snapshot) {
  const repositories = Array.isArray(snapshot.repositories) ? snapshot.repositories : [];
  const workItems = Array.isArray(snapshot.workItems) ? snapshot.workItems : [];
  const activity = Array.isArray(snapshot.activity) ? snapshot.activity : [];
  const repositoriesById = new Map(repositories.map((repo) => [repo.id, repo]));
  const referenceTime = snapshot.liveFetchedAt || snapshot.generatedAt;

  renderWorld(repositories, workItems, activity, referenceTime);
  renderGates(workItems, repositoriesById);
  renderActivity(activity, repositoriesById);
  renderStats(snapshot.stats);
  repositoryCount.textContent = `${repositories.length} repositories`;

  if (repositories.length === 0) {
    workspaceMessage.hidden = false;
    workspaceMessage.textContent = "公開対象のrepositoryは0件です。";
    return;
  }
  workspaceMessage.hidden = true;
}

async function resolveLiveEndpoint() {
  if (liveEndpointResolved) return liveEndpoint;
  liveEndpointResolved = true;
  if (window.location.hostname.endsWith(".vercel.app")) {
    liveEndpoint = "/api/dashboard-live";
    return liveEndpoint;
  }
  try {
    const response = await fetch(LIVE_CONFIG_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const config = await response.json();
    liveEndpoint = typeof config.endpoint === "string" && config.endpoint.startsWith("https://") ? config.endpoint : null;
  } catch (error) {
    console.warn("dashboard live endpoint config unavailable", error);
    liveEndpoint = null;
  }
  return liveEndpoint;
}

export async function refreshLiveState({ force = false } = {}) {
  if (!baselineSnapshot) return null;
  if (!force && lastLiveSuccessAt && Date.now() - lastLiveSuccessAt < MIN_LIVE_SUCCESS_AGE_MS) return null;
  if (liveRequest) return liveRequest;

  const endpoint = await resolveLiveEndpoint();
  if (!endpoint) {
    renderLiveFailure("endpoint未設定");
    return null;
  }

  const sequence = ++liveRequestSequence;
  liveRequest = (async () => {
    try {
      const response = await fetch(endpoint, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const live = await response.json();
      const merged = mergeLiveSnapshot(baselineSnapshot, live);
      if (sequence < latestAppliedSequence) return null;
      latestAppliedSequence = sequence;
      lastLiveSuccessAt = Date.now();
      renderDashboard(merged);
      renderSnapshotMeta(baselineSnapshot);
      renderLiveMeta(live.fetchedAt);
      return merged;
    } catch (error) {
      if (sequence >= latestAppliedSequence) renderLiveFailure();
      console.error("dashboard live refresh failed", error);
      return null;
    } finally {
      if (sequence === liveRequestSequence) liveRequest = null;
    }
  })();
  return liveRequest;
}

async function loadDashboard() {
  try {
    const response = await fetch("./dashboard.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    baselineSnapshot = await response.json();
    renderDashboard(baselineSnapshot);
    renderSnapshotMeta(baselineSnapshot);
    await refreshLiveState({ force: true });
  } catch (error) {
    renderDashboard({ repositories: [], workItems: [], activity: [], stats: null });
    snapshotStatus.dataset.state = "failed";
    snapshotStatus.textContent = "更新失敗";
    snapshotGeneratedAt.removeAttribute("datetime");
    snapshotGeneratedAt.textContent = "Snapshot: 取得できません";
    liveFetchedAt.removeAttribute("datetime");
    liveFetchedAt.textContent = "Live: baselineなし";
    workspaceMessage.hidden = false;
    workspaceMessage.textContent = "dashboard.json を読み込めませんでした。最新成功データとして扱いません。";
    console.error(error);
  }
}

window.addEventListener("dashboard:refresh-live", () => refreshLiveState());
loadDashboard();
