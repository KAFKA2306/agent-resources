const groupsRoot = document.querySelector("#project-groups");
const repositoryCount = document.querySelector("#repository-count");
const snapshotStatus = document.querySelector("#snapshot-status");
const workspaceMessage = document.querySelector("#workspace-message");

function groupRepositories(repositories) {
  const groups = new Map();
  for (const repository of repositories) {
    const group = repository.group || "other";
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push(repository);
  }
  return [...groups.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([group, items]) => [
      group,
      items.sort((left, right) => left.name.localeCompare(right.name)),
    ]);
}

function repositoryCard(repository) {
  const link = document.createElement("a");
  link.className = "repository-card";
  link.href = repository.url;
  link.target = "_blank";
  link.rel = "noreferrer";

  const name = document.createElement("strong");
  name.textContent = repository.name;
  const owner = document.createElement("span");
  owner.textContent = repository.owner;

  link.append(name, owner);
  return link;
}

function renderRepositories(repositories) {
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
    for (const repository of items) grid.append(repositoryCard(repository));

    section.append(heading, grid);
    groupsRoot.append(section);
  }
}

async function loadDashboard() {
  try {
    const response = await fetch("./dashboard.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const snapshot = await response.json();
    renderRepositories(Array.isArray(snapshot.repositories) ? snapshot.repositories : []);
    snapshotStatus.textContent = "読込済";
  } catch (error) {
    renderRepositories([]);
    snapshotStatus.textContent = "読込失敗";
    workspaceMessage.hidden = false;
    workspaceMessage.textContent = "dashboard.json を読み込めませんでした。";
    console.error(error);
  }
}

loadDashboard();
