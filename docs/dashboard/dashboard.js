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
const ACTIVITY_COUNT_LABELS = { issue: "Issue", pull_request: "PR", workflow_run: "Run" };
const WORK_ITEM_LABELS = { issue: "Issue", pull_request: "Pull Request", workflow_run: "Workflow Run" };
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

function formatWorkItemAge(value) {
  const updated = new Date(value);
  if (Number.isNaN(updated.getTime())) return "更新時刻不明";
  const ageMs = Math.max(0, Date.now() - updated.getTime());
  const minutes = Math.floor(ageMs / (60 * 1000));
  if (minutes < 60) return `${minutes}分前に更新`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}時間前に更新`;
  return `${Math.floor(hours / 24)}日前に更新`;
}

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
    const row = document.createElement("article");
    row.className = "gate-item";
    const repo = repositoriesById.get(item.repositoryId);

    const itemHeading = document.createElement("div");
    itemHeading.className = "gate-item-heading";
    const link = document.createElement("a");
    link.className = "gate-item-link";
    link.href = item.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = `${repo ? repo.name : "unknown"} · ${item.title}`;
    itemHeading.append(link);

    const meta = document.createElement("div");
    meta.className = "gate-item-meta";
    const kind = document.createElement("span");
    kind.textContent = WORK_ITEM_LABELS[item.kind] || item.kind;
    const state = document.createElement("span");
    state.textContent = item.state;
    const updated = document.createElement("time");
    if (item.updatedAt) updated.dateTime = item.updatedAt;
    updated.textContent = formatWorkItemAge(item.updatedAt);
    meta.append(kind, state, updated);

    const reason = document.createElement("p");
    reason.className = "gate-item-reason";
    reason.textContent = item.laneReason || "理由は取得できませんでした。";

    row.append(itemHeading, meta, reason);
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
  return new Intl.DateTimeFormat("ja-JP", { hour: "2-digit", minute: "2-digit" }).format(date);
}

function localDayKey(value) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "unknown";
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatActivityDay(dayKey) {
  if (dayKey === "unknown") return "日付不明";
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (dayKey === localDayKey(today)) return "今日";
  if (dayKey === localDayKey(yesterday)) return "昨日";
  const [year, month, day] = dayKey.split("-").map(Number);
  return new Intl.DateTimeFormat("ja-JP", { month: "numeric", day: "numeric", weekday: "short" }).format(
    new Date(year, month - 1, day),
  );
}

function formatActivityCounts(items) {
  const counts = { issue: 0, pull_request: 0, workflow_run: 0 };
  for (const item of items) {
    if (Object.hasOwn(counts, item.kind)) counts[item.kind] += 1;
  }
  return Object.entries(counts)
    .filter(([, count]) => count > 0)
    .map(([kind, count]) => `${ACTIVITY_COUNT_LABELS[kind]} ${count}`)
    .join(" · ");
}

function createActivityItem(item) {
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
  link.append(meta, summary);
  return link;
}

function groupActivity(items) {
  const days = new Map();
  for (const item of items) {
    const dayKey = localDayKey(item.occurredAt);
    if (!days.has(dayKey)) days.set(dayKey, { items: [], repositories: new Map() });
    const day = days.get(dayKey);
    day.items.push(item);
    if (!day.repositories.has(item.repositoryId)) day.repositories.set(item.repositoryId, []);
    day.repositories.get(item.repositoryId).push(item);
  }
  return days;
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

  for (const [dayKey, day] of groupActivity(items)) {
    const daySection = document.createElement("section");
    daySection.className = "activity-day";
    const dayHeading = document.createElement("div");
    dayHeading.className = "activity-day-heading";
    const dayName = document.createElement("strong");
    dayName.textContent = formatActivityDay(dayKey);
    const daySummary = document.createElement("span");
    daySummary.textContent = `${day.repositories.size} repos · ${formatActivityCounts(day.items)}`;
    dayHeading.append(dayName, daySummary);
    daySection.append(dayHeading);

    for (const [repositoryId, repositoryItems] of day.repositories) {
      const card = document.createElement("article");
      card.className = "activity-repository-card";
      const repositoryHeading = document.createElement("div");
      repositoryHeading.className = "activity-repository-heading";
      const repositoryName = document.createElement("strong");
      repositoryName.textContent = repositoriesById.get(repositoryId)?.name || "unknown";
      const repositorySummary = document.createElement("span");
      repositorySummary.textContent = `${repositoryItems.length}件 · ${formatActivityCounts(repositoryItems)}`;
      repositoryHeading.append(repositoryName, repositorySummary);
      card.append(repositoryHeading, createActivityItem(repositoryItems[0]));

      if (repositoryItems.length > 1) {
        const details = document.createElement("details");
        details.className = "activity-more";
        const summary = document.createElement("summary");
        summary.textContent = `残り${repositoryItems.length - 1}件を見る`;
        const list = document.createElement("div");
        list.className = "activity-more-list";
        for (const item of repositoryItems.slice(1)) list.append(createActivityItem(item));
        details.append(summary, list);
        card.append(details);
      }
      daySection.append(card);
    }
    activityFeed.append(daySection);
  }
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

  const sequence = ++liveRequestSequence;
  liveRequest = (async () => {
    try {
      const endpoint = await resolveLiveEndpoint();
      if (!endpoint) {
        renderLiveFailure("endpoint未設定");
        return null;
      }
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
