const assetVersion = encodeURIComponent(new URL(import.meta.url).searchParams.get("v") || Date.now().toString());
const [
  { compareWorkItems },
  { classifySnapshot },
  { renderStats },
  { createPublicSurfaceLinks, renderWorld },
] = await Promise.all([
  import(`./ranking.js?v=${assetVersion}`),
  import(`./snapshot-status.js?v=${assetVersion}`),
  import(`./stats.js?v=${assetVersion}`),
  import(`./world.js?v=${assetVersion}`),
]);

const repositoryCount = document.querySelector("#repository-count");
const snapshotStatus = document.querySelector("#snapshot-status");
const snapshotGeneratedAt = document.querySelector("#snapshot-generated-at");
const workspaceMessage = document.querySelector("#workspace-message");
const laneGates = document.querySelector("#lane-gates");
const gateDetail = document.querySelector("#gate-detail");
const actionCoverage = document.querySelector("#action-coverage");
const primaryAction = document.querySelector("#primary-action");
const primaryActionTitle = document.querySelector("#primary-action-title");
const primaryActionItem = document.querySelector("#primary-action-item");
const activityFeed = document.querySelector("#activity-feed");
const heroRepositoryTotal = document.querySelector("#hero-repository-total");
const heroActivityTotal = document.querySelector("#hero-activity-total");
const heroMotionLabel = document.querySelector("#hero-motion-label");

const ACTIVITY_LABELS = { issue: "Issue", pull_request: "Pull Request", workflow_run: "Workflow Run" };
const ACTIVITY_COUNT_LABELS = { issue: "Issue", pull_request: "PR", workflow_run: "Run" };
const GATES = [
  { lane: "waiting", label: "未解決PR", detailLabel: "未解決PR" },
  { lane: "failed", label: "実行の失敗", detailLabel: "失敗した実行" },
  { lane: "done", label: "終了した実行", detailLabel: "終了した実行" },
];
const NEXT_ACTION = {
  workflow_run: "Actionsの実行ログを開く",
  pull_request: "PRの変更とチェックを開く",
  issue: "Issueを開く",
};
const LANE_REASONS = {
  open_pull_request: "PRが開いています。",
  workflow_failed: "実行が失敗しました。",
  workflow_cancelled: "実行が中止されました。",
  workflow_completed: "実行が完了しました。",
  workflow_skipped: "実行がスキップされました。",
};
let visibleSnapshot = null;

function repositoryLabel(repository) {
  if (!repository) return "unknown";
  return repository.owner ? `${repository.owner} / ${repository.name}` : repository.name;
}

function formatWorkItemAge(value, observedAt) {
  const updated = new Date(value);
  if (Number.isNaN(updated.getTime())) return "更新時刻不明";
  const observed = new Date(observedAt);
  if (Number.isNaN(observed.getTime())) return "更新時刻不明";
  const ageMs = Math.max(0, observed.getTime() - updated.getTime());
  const minutes = Math.floor(ageMs / (60 * 1000));
  if (minutes < 60) return `${minutes}分前に更新`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}時間前に更新`;
  return `${Math.floor(hours / 24)}日前に更新`;
}

function createGateItem(item, repositoriesById, includePublicSurfaces = true) {
  const repo = repositoriesById.get(item.repositoryId);
  const row = document.createElement("article");
  row.className = "gate-item";

  const meta = document.createElement("div");
  meta.className = "gate-item-meta";
  const owner = document.createElement("span");
  owner.className = "gate-item-owner";
  owner.textContent = repositoryLabel(repo);
  const updated = document.createElement("time");
  if (item.updatedAt) updated.dateTime = item.updatedAt;
  updated.textContent = formatWorkItemAge(item.updatedAt, visibleSnapshot?.snapshot.generatedAt);
  meta.append(owner, updated);

  const title = document.createElement("strong");
  title.className = "gate-item-title";
  title.textContent = item.title;

  const reason = document.createElement("p");
  reason.className = "gate-item-reason";
  reason.textContent = LANE_REASONS[item.laneReason] || "GitHubで状態を確認してください。";

  const link = document.createElement("a");
  link.className = "gate-item-link";
  link.href = item.url;
  link.textContent = NEXT_ACTION[item.kind] || "GitHubの記録を開く";

  row.append(meta, title, reason, link);
  const publicSurfaceLinks = includePublicSurfaces && repo ? createPublicSurfaceLinks(repo) : null;
  if (publicSurfaceLinks) row.append(publicSurfaceLinks);
  return row;
}

function renderPrimaryAction(failed, waiting, repositoriesById, snapshot) {
  const stored = classifySnapshot(snapshot.generatedAt);
  const savedAt = stored.generated
    ? `保存時刻 ${formatSnapshotTime(stored.generated)} JST`
    : "保存時刻不明";
  let status = `GitHubの現在状態は未確認です。公開snapshotの${savedAt}を表示しています。`;

  const item = failed[0] || waiting[0];
  if (!item) {
    status += stored.generated
      ? " 保存データに失敗した実行・未解決PRはありません。現在の件数は未確認です。"
      : " 現在の対応件数は未確認です。";
  }
  actionCoverage.textContent = status;
  const linkHadFocus = primaryAction.contains(document.activeElement);
  primaryAction.hidden = !item;
  primaryActionItem.replaceChildren();
  if (!item) return;

  primaryActionTitle.textContent = item.lane === "failed"
    ? "Snapshot上の確認候補 · 失敗した実行"
    : "Snapshot上の確認候補 · 未解決PR";
  primaryActionItem.append(createGateItem(item, repositoriesById, false));
  if (linkHadFocus) primaryActionItem.querySelector(".gate-item-link").focus({ preventScroll: true });
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
  for (const item of items) {
    list.append(createGateItem(item, repositoriesById));
  }
  gateDetail.append(list);
}

function renderGates(workItems, repositoriesById, snapshot) {
  laneGates.replaceChildren();
  gateDetail.hidden = true;
  const ordered = workItems.slice().sort(compareWorkItems);
  const failed = ordered.filter((item) => item.lane === "failed");
  const waiting = ordered.filter((item) => item.lane === "waiting");
  renderPrimaryAction(failed, waiting, repositoriesById, snapshot);

  const itemsByLane = { failed, waiting, done: ordered.filter((item) => item.lane === "done") };
  for (const gate of GATES) {
    const items = itemsByLane[gate.lane];
    const detailLabel = gate.detailLabel;
    const button = document.createElement("button");
    button.className = "lane-gate";
    button.dataset.lane = gate.lane;
    button.type = "button";
    button.setAttribute("aria-pressed", "false");
    button.setAttribute("aria-label", `${detailLabel}: ${items.length}件`);
    button.innerHTML = `<span>${gate.label}</span><strong>${items.length}</strong>`;
    button.addEventListener("click", () => {
      for (const candidate of laneGates.querySelectorAll("button[data-lane]")) {
        candidate.setAttribute("aria-pressed", String(candidate === button));
      }
      showGateItems(detailLabel, items, repositoriesById);
    });
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
    .sort((a, b) => a.occurredAt.localeCompare(b.occurredAt));

  if (items.length === 0) {
    const empty = document.createElement("p");
    empty.className = "muted activity-empty";
    empty.textContent = "NO SIGNAL";
    activityFeed.append(empty);
    return;
  }

  const SVG_NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.classList.add("activity-pulse-plot");
  svg.setAttribute("viewBox", "0 0 1000 290");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `${items.length} GitHub activity events over the last seven days`);

  const days = [...new Set(items.map((item) => localDayKey(item.occurredAt)))].sort();
  const dayIndex = new Map(days.map((day, index) => [day, index]));
  const xForDay = (day) => {
    const index = dayIndex.get(day) ?? 0;
    if (days.length <= 1) return 520;
    return 100 + (index / (days.length - 1)) * 840;
  };
  const rows = {
    workflow_run: { y: 78, label: "RUN" },
    pull_request: { y: 155, label: "PR" },
    issue: { y: 232, label: "ISSUE" },
  };

  for (const { y, label } of Object.values(rows)) {
    const guide = document.createElementNS(SVG_NS, "line");
    guide.setAttribute("x1", "92");
    guide.setAttribute("x2", "954");
    guide.setAttribute("y1", String(y));
    guide.setAttribute("y2", String(y));
    guide.classList.add("pulse-guide");
    svg.append(guide);

    const text = document.createElementNS(SVG_NS, "text");
    text.setAttribute("x", "20");
    text.setAttribute("y", String(y + 4));
    text.classList.add("pulse-axis-label");
    text.textContent = label;
    svg.append(text);
  }

  const dailyCounts = days.map((day) => items.filter((item) => localDayKey(item.occurredAt) === day).length);
  const maxDaily = Math.max(1, ...dailyCounts);
  const envelope = document.createElementNS(SVG_NS, "polyline");
  envelope.classList.add("pulse-envelope");
  envelope.setAttribute(
    "points",
    days.map((day, index) => {
      const x = xForDay(day);
      const y = 40 - (dailyCounts[index] / maxDaily) * 22;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" "),
  );
  svg.append(envelope);

  for (const day of days) {
    const x = xForDay(day);
    const tick = document.createElementNS(SVG_NS, "line");
    tick.setAttribute("x1", String(x));
    tick.setAttribute("x2", String(x));
    tick.setAttribute("y1", "50");
    tick.setAttribute("y2", "252");
    tick.classList.add("pulse-day-guide");
    svg.append(tick);

    const label = document.createElementNS(SVG_NS, "text");
    label.setAttribute("x", String(x));
    label.setAttribute("y", "278");
    label.setAttribute("text-anchor", "middle");
    label.classList.add("pulse-day-label");
    label.textContent = formatActivityDay(day).replace("今日", "TODAY").replace("昨日", "YDAY");
    svg.append(label);
  }

  const stackByCell = new Map();
  for (const item of items) {
    const row = rows[item.kind];
    if (!row) continue;
    const day = localDayKey(item.occurredAt);
    const baseX = xForDay(day);
    const cellKey = `${day}:${item.kind}`;
    const offsetIndex = stackByCell.get(cellKey) || 0;
    stackByCell.set(cellKey, offsetIndex + 1);
    const columns = 9;
    const dx = ((offsetIndex % columns) - (columns - 1) / 2) * 9;
    const dy = Math.floor(offsetIndex / columns) * -10;
    const x = baseX + dx;
    const y = row.y + dy;
    const repo = repositoriesById.get(item.repositoryId);

    const anchor = document.createElementNS(SVG_NS, "a");
    anchor.setAttribute("href", item.url);
    anchor.setAttribute("target", "_blank");
    anchor.setAttribute("rel", "noopener noreferrer");
    anchor.classList.add("activity-pulse-point", `is-${item.kind}`);
    anchor.setAttribute(
      "aria-label",
      `${ACTIVITY_LABELS[item.kind]}: ${repositoryLabel(repo)}. ${item.summary || ""}. ${formatActivityTime(item.occurredAt)}`,
    );

    const halo = document.createElementNS(SVG_NS, "circle");
    halo.setAttribute("cx", x.toFixed(1));
    halo.setAttribute("cy", y.toFixed(1));
    halo.setAttribute("r", "8");
    halo.classList.add("pulse-point-halo");

    const dot = document.createElementNS(SVG_NS, "circle");
    dot.setAttribute("cx", x.toFixed(1));
    dot.setAttribute("cy", y.toFixed(1));
    dot.setAttribute("r", "4.2");
    dot.classList.add("pulse-point-dot");

    const title = document.createElementNS(SVG_NS, "title");
    title.textContent = `${repositoryLabel(repo)} · ${ACTIVITY_LABELS[item.kind]} · ${formatActivityTime(item.occurredAt)}\n${item.summary || ""}`;
    anchor.append(title, halo, dot);
    svg.append(anchor);
  }

  const counter = document.createElement("div");
  counter.className = "pulse-counter";
  counter.innerHTML = `<strong>${items.length}</strong><span>SIGNALS / 7D</span>`;

  activityFeed.append(svg, counter);
}

function formatSnapshotTime(date) {
  return new Intl.DateTimeFormat("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZone: "Asia/Tokyo",
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

function renderDashboard(snapshot) {
  const repositories = Array.isArray(snapshot.repositories) ? snapshot.repositories : [];
  const workItems = Array.isArray(snapshot.workItems) ? snapshot.workItems : [];
  const activity = Array.isArray(snapshot.activity) ? snapshot.activity : [];
  const repositoriesById = new Map(repositories.map((repo) => [repo.id, repo]));
  const referenceTime = snapshot.generatedAt;
  visibleSnapshot = { workItems, repositoriesById, snapshot };

  renderGates(workItems, repositoriesById, snapshot);
  renderWorld(repositories, workItems, activity, referenceTime);
  renderActivity(activity, repositoriesById);
  renderStats(snapshot.stats);
  const factoryActivity = Math.min(1, activity.length / 70);
  const factoryMotion = activity.length === 0 ? "idle" : factoryActivity >= 0.65 ? "hot" : "active";
  document.documentElement.dataset.factoryActivity = factoryActivity.toFixed(3);
  document.documentElement.dataset.factoryMotion = factoryMotion;
  heroRepositoryTotal.textContent = String(repositories.length);
  heroActivityTotal.textContent = String(activity.length);
  heroMotionLabel.textContent = ({ idle: "QUIET", active: "RECENT", hot: "SURGE" })[factoryMotion];
  repositoryCount.textContent = `${repositories.length} repositories`;

  if (repositories.length === 0) {
    workspaceMessage.hidden = false;
    workspaceMessage.textContent = "公開対象のrepositoryは0件です。";
    return;
  }
  workspaceMessage.hidden = true;
}

async function loadDashboard() {
  try {
    const response = await fetch("./dashboard.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const snapshot = await response.json();
    renderDashboard(snapshot);
    renderSnapshotMeta(snapshot);
  } catch (error) {
    renderDashboard({ repositories: [], workItems: [], activity: [], stats: null });
    snapshotStatus.dataset.state = "failed";
    snapshotStatus.textContent = "更新失敗";
    snapshotGeneratedAt.removeAttribute("datetime");
    snapshotGeneratedAt.textContent = "Snapshot: 取得できません";
    workspaceMessage.hidden = false;
    workspaceMessage.textContent = "dashboard.json を読み込めませんでした。最新成功データとして扱いません。";
    console.error(error);
  }
}

loadDashboard();
