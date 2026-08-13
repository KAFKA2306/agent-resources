const SOURCE_COMMIT = "3e70694f9c7487bfa8e72ee57e9004601ce030e2";
const RAW_BASE = `https://raw.githubusercontent.com/KAFKA2306/prompt-vault/${SOURCE_COMMIT}/artifacts`;
const REFERENCE_TEXTURES = [
  `${RAW_BASE}/110_morning_tweet_window_topdown.png`,
  `${RAW_BASE}/169_096_art_direction_desk_review.png`,
  `${RAW_BASE}/172_105_tweetsdb_idea_map.png`,
  `${RAW_BASE}/254_kafka_night_game_room_ui.png`,
];

const KIND_LABELS = { issue: "ISSUE", pull_request: "PR", workflow_run: "RUN" };
const LANE_LABELS = { working: "作業中", waiting: "判断待ち", done: "完了", failed: "要確認" };

function groupedRepositories(repositories) {
  const groups = new Map();
  for (const repository of repositories) {
    const group = repository.group || "other";
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push(repository);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([group, items]) => [group, items.slice().sort((a, b) => a.name.localeCompare(b.name))]);
}

function createAgent(item) {
  const link = document.createElement("a");
  link.className = "world-agent";
  link.dataset.lane = item.lane;
  link.href = item.url;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.title = item.title;

  const figure = document.createElement("span");
  figure.className = "world-agent-figure";
  figure.setAttribute("aria-hidden", "true");

  const copy = document.createElement("span");
  copy.className = "world-agent-copy";
  const title = document.createElement("strong");
  title.textContent = item.title;
  const status = document.createElement("small");
  status.textContent = `${KIND_LABELS[item.kind] || "ITEM"} · ${LANE_LABELS[item.lane] || "要確認"}`;
  copy.append(title, status);
  link.append(figure, copy);
  return link;
}

function createStation(repository, workItems) {
  const station = document.createElement("article");
  station.className = "world-station";

  const repositoryLink = document.createElement("a");
  repositoryLink.className = "world-station-link";
  repositoryLink.href = repository.url;
  repositoryLink.target = "_blank";
  repositoryLink.rel = "noreferrer";
  const name = document.createElement("strong");
  name.textContent = repository.name;
  const count = document.createElement("span");
  count.textContent = `${workItems.length} agents`;
  repositoryLink.append(name, count);

  const agents = document.createElement("div");
  agents.className = "world-agents";
  agents.setAttribute("aria-label", `${repository.name} agents`);
  for (const item of workItems.slice().sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))) {
    agents.append(createAgent(item));
  }

  station.append(repositoryLink, agents);
  return station;
}

function createZone(group, repositories, workByRepository, index) {
  const zone = document.createElement("section");
  zone.className = "world-zone";

  const reference = document.createElement("img");
  reference.className = "world-reference";
  reference.src = REFERENCE_TEXTURES[index % REFERENCE_TEXTURES.length];
  reference.alt = "";
  reference.loading = "lazy";
  reference.decoding = "async";
  reference.setAttribute("aria-hidden", "true");

  const content = document.createElement("div");
  content.className = "world-zone-content";
  const heading = document.createElement("div");
  heading.className = "world-zone-heading";
  const name = document.createElement("strong");
  name.textContent = group;
  const meta = document.createElement("span");
  meta.textContent = `${repositories.length} stations`;
  heading.append(name, meta);

  const stations = document.createElement("div");
  stations.className = "world-stations";
  for (const repository of repositories) {
    stations.append(createStation(repository, workByRepository.get(repository.id) || []));
  }
  content.append(heading, stations);
  zone.append(reference, content);
  return zone;
}

export function renderWorld(repositories, workItems) {
  const root = document.querySelector("#agent-world-zones");
  const summary = document.querySelector("#agent-world-summary");
  if (!root || !summary) return;

  root.replaceChildren();
  summary.textContent = `${workItems.length} agents`;

  if (repositories.length === 0) {
    const empty = document.createElement("p");
    empty.className = "world-empty muted";
    empty.textContent = "表示できるproject区画は0件です。";
    root.append(empty);
    return;
  }

  const workByRepository = new Map();
  for (const item of workItems) {
    if (!workByRepository.has(item.repositoryId)) workByRepository.set(item.repositoryId, []);
    workByRepository.get(item.repositoryId).push(item);
  }

  groupedRepositories(repositories).forEach(([group, items], index) => {
    root.append(createZone(group, items, workByRepository, index));
  });
}
