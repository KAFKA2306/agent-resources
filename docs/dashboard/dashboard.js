import { classifySnapshot } from "./snapshot-status.js";
import { renderStats } from "./stats.js";

const groupsRoot = document.querySelector("#project-groups");
const repositoryCount = document.querySelector("#repository-count");
const snapshotStatus = document.querySelector("#snapshot-status");
const snapshotGeneratedAt = document.querySelector("#snapshot-generated-at");
const workspaceMessage = document.querySelector("#workspace-message");
const laneGates = document.querySelector("#lane-gates");
const gateDetail = document.querySelector("#gate-detail");
const activityFeed = document.querySelector("#activity-feed");

const KIND_LABELS = { issue: "ISSUE", pull_request: "PR", workflow_run: "RUN" };
const ACTIVITY_LABELS = { issue: "Issue", pull_request: "Pull Request", workflow_run: "Workflow Run" };
const ACTIVITY_LIMIT = 20;
const GATES = [
  { lane: "waiting", label: "判断待ち" },
  { lane: "done", label: "完了報告" },
  { lane: "failed", label: "失敗・要確認" },
];

function groupRepositories(repositories) {
  const groups = new Map();
  for (const repository of repositories) {
    const group = repository.group || "other";
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push(repository);
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([group, items]) => [group, items.sort((a, b) => a.name.localeCompare(b.name))]);
}

function workItemAgent(item, repository) {
  const link = document.createElement("a");
  link.className = "work-agent";
  link.dataset.kind = item.kind;
  link.href = item.url;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.title = `${repository.name}: ${item.title}`;
  const badge = document.createElement("span");
  badge.className = "agent-badge";
  badge.textContent = KIND_LABELS[item.kind] || "ITEM";
  const copy = document.createElement("span");
  copy.className = "agent-copy";
  const title = document.createElement("strong");
  title.textContent = item.title;
  const repo = document.createElement("small");
  repo.textContent = repository.name;
  copy.append(title, repo);
  link.append(badge, copy);
  return link;
}

function repositoryCard(repository, workItems) {
  const card = document.createElement("article");
  card.className = "repository-card";
  const link = document.createElement("a");
  link.className = "repository-link";
  link.href = repository.url;
  link.target = "_blank";
  link.rel = "noreferrer";
  const name = document.createElement("strong");
  name.textContent = repository.name;
  const owner = document.createElement("span");
  owner.textContent = repository.owner;
  link.append(name, owner);
  const agents = document.createElement("div");
  agents.className = "agent-list";
  agents.setAttribute("aria-label", `${repository.name} work items`);
  for (const item of workItems) agents.append(workItemAgent(item, repository));
  card.append(link, agents);
  return card;
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
    const link = document.createElement("a");
    link.href = item.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    const repo = repositoriesById.get(item.repositoryId);
    link.textContent = `${repo ? repo.name : "unknown"} · ${item.title}`;
    list.append(link);
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
  snapshotStatus.dataset.state = freshness.state;
  snapshotStatus.textContent = freshness.label;
  if (!freshness.generated) {
    snapshotGeneratedAt.removeAttribute("datetime");
    snapshotGeneratedAt.textContent = "生成時刻: 不明";
    return;
  }
  snapshotGeneratedAt.dateTime = freshness.generated.toISOString();
  snapshotGeneratedAt.textContent = `生成時刻: ${formatSnapshotTime(freshness.generated)}`;
}

function renderActivity(activity) {
  activityFeed.replaceChildren();
  const items = activity.filter((item) => ACTIVITY_LABELS[item.kind]).slice().sort((a, b) => b.occurredAt.localeCompare(a.occurredAt)).slice(0, ACTIVITY_LIMIT);
  if (items.length === 0) {
    const empty = document.createElement("p");
    empty.className = "muted activity-empty";
    empty.textContent = "最近の活動は0件です。";
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
    repo.textContent = item.repositoryName;
    link.append(meta, summary, repo);
    activityFeed.append(link);
  }
}

function renderDashboard(snapshot) {
  const repositories = Array.isArray(snapshot.repositories) ? snapshot.repositories : [];
  const workItems = Array.isArray(snapshot.workItems) ? snapshot.workItems : [];
  const activity = Array.isArray(snapshot.activity) ? snapshot.activity : [];
  const repositoriesById = new Map(repositories.map((repo) => [repo.id, repo]));
  const workByRepository = new Map();
  for (const item of workItems) {
    if (!workByRepository.has(item.repositoryId)) workByRepository.set(item.repositoryId, []);
    workByRepository.get(item.repositoryId).push(item);
  }
  renderGates(workItems, repositoriesById);
  renderActivity(activity);
  renderStats(snapshot.stats);
  groupsRoot.replaceChildren();
  repositoryCount.textContent = `${repositories.length} repositories`;
  if (repositories.length === 0) {
    workspaceMessage.hidden = false;
    workspaceMessage.textContent = "公開対象のrepositoryは0件です。";
    return;
  }
  workspaceMessage.hidden = true;
  for (const [group, items] of groupRepositories(repositories)) {
    const section = document.createElement("section");
    section.className = "project-group";
    const heading = document.createElement("div");
    heading.className = "group-heading";
    const title = document.createElement("h3");
    title.textContent = group;
    const count = document.createElement("span");
    count.textContent = `${items.length}`;
    heading.append(title, count);
    const grid = document.createElement("div");
    grid.className = "repository-grid";
    for (const repository of items) {
      const repositoryItems = (workByRepository.get(repository.id) || []).slice().sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
      grid.append(repositoryCard(repository, repositoryItems));
    }
    section.append(heading, grid);
    groupsRoot.append(section);
  }
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
    snapshotGeneratedAt.textContent = "生成時刻: 取得できません";
    workspaceMessage.hidden = false;
    workspaceMessage.textContent = "dashboard.json を読み込めませんでした。最新成功データとして扱いません。";
    console.error(error);
  }
}

loadDashboard();
