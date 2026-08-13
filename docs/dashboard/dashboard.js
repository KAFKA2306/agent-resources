const groupsRoot = document.querySelector("#project-groups");
const repositoryCount = document.querySelector("#repository-count");
const snapshotStatus = document.querySelector("#snapshot-status");
const workspaceMessage = document.querySelector("#workspace-message");

const KIND_LABELS = {
  issue: "ISSUE",
  pull_request: "PR",
  workflow_run: "RUN",
};

function groupRepositories(repositories) {
  const groups = new Map();
  for (const repository of repositories) {
    const group = repository.group || "other";
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push(repository);
  }
  return [...groups.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([group, items]) => [group, items.sort((left, right) => left.name.localeCompare(right.name))]);
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

function renderDashboard(snapshot) {
  const repositories = Array.isArray(snapshot.repositories) ? snapshot.repositories : [];
  const workItems = Array.isArray(snapshot.workItems) ? snapshot.workItems : [];
  const workByRepository = new Map();
  for (const item of workItems) {
    if (!workByRepository.has(item.repositoryId)) workByRepository.set(item.repositoryId, []);
    workByRepository.get(item.repositoryId).push(item);
  }

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
      const repositoryItems = (workByRepository.get(repository.id) || [])
        .slice()
        .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
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
    snapshotStatus.textContent = "読込済";
  } catch (error) {
    renderDashboard({ repositories: [], workItems: [] });
    snapshotStatus.textContent = "読込失敗";
    workspaceMessage.hidden = false;
    workspaceMessage.textContent = "dashboard.json を読み込めませんでした。";
    console.error(error);
  }
}

loadDashboard();
