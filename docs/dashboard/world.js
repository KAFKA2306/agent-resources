import { compareWorkItems, rankRepositories, repositoryHeat } from "./ranking.js";

const ASSET_ROOT = "./assets/agent-world";

const ASSET_BY_ID = Object.freeze({
  "role.issue-working.v1": `${ASSET_ROOT}/role-issue-working.svg`,
  "role.pull-request-review.v1": `${ASSET_ROOT}/role-pull-request-review.svg`,
  "role.workflow-terminal.v1": `${ASSET_ROOT}/role-workflow-terminal.svg`,
  "state.working.v1": `${ASSET_ROOT}/state-working.svg`,
  "state.waiting.v1": `${ASSET_ROOT}/state-waiting.svg`,
  "state.done.v1": `${ASSET_ROOT}/state-done.svg`,
  "state.failed.v1": `${ASSET_ROOT}/state-failed.svg`,
  "scene.desk.v1": `${ASSET_ROOT}/scene-desk.svg`,
  "scene.review-bench.v1": `${ASSET_ROOT}/scene-review-bench.svg`,
  "scene.terminal.v1": `${ASSET_ROOT}/scene-terminal.svg`,
  "scene.sign.v1": `${ASSET_ROOT}/scene-sign.svg`,
  "scene.floor.v1": `${ASSET_ROOT}/scene-floor.svg`,
  "prop.small-pack.v1": `${ASSET_ROOT}/prop-pack.svg`,
});

const ROLE_ASSET_IDS = Object.freeze({
  issue: "role.issue-working.v1",
  pull_request: "role.pull-request-review.v1",
  workflow_run: "role.workflow-terminal.v1",
});
const STATE_ASSET_IDS = Object.freeze({
  working: "state.working.v1",
  waiting: "state.waiting.v1",
  done: "state.done.v1",
  failed: "state.failed.v1",
});
const KIND_LABELS = { issue: "ISSUE", pull_request: "PR", workflow_run: "RUN" };
const LANE_LABELS = { working: "作業中", waiting: "判断待ち", done: "完了", failed: "失敗・要確認" };
const UNCLASSIFIED_GROUP = "unclassified";

function resolveAsset(assetId) {
  const src = ASSET_BY_ID[assetId];
  if (!src) throw new Error(`Unknown Agent World asset id: ${assetId}`);
  return src;
}

function createAssetImage(assetId, className, onLoad = null) {
  const image = document.createElement("img");
  image.className = className;
  image.dataset.assetId = assetId;
  image.alt = "";
  image.loading = "lazy";
  image.decoding = "async";
  image.setAttribute("aria-hidden", "true");
  image.addEventListener(
    "load",
    () => {
      image.dataset.assetState = "loaded";
      if (onLoad) onLoad();
    },
    { once: true },
  );
  image.addEventListener(
    "error",
    () => {
      image.dataset.assetState = "failed";
      image.hidden = true;
    },
    { once: true },
  );
  image.src = resolveAsset(assetId);
  return image;
}

function groupedRepositories(repositories, workItems, activity, generatedAt) {
  const groups = new Map();
  for (const repository of repositories) {
    const group = repository.group || UNCLASSIFIED_GROUP;
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push(repository);
  }
  return [...groups.entries()]
    .map(([group, items]) => [group, rankRepositories(items, workItems, activity, generatedAt)])
    .sort(([aGroup, aItems], [bGroup, bItems]) => {
      if (aGroup === UNCLASSIFIED_GROUP && bGroup !== UNCLASSIFIED_GROUP) return 1;
      if (bGroup === UNCLASSIFIED_GROUP && aGroup !== UNCLASSIFIED_GROUP) return -1;
      const aHeat = aItems.length ? repositoryHeat(aItems[0], workItems, activity, generatedAt) : 0;
      const bHeat = bItems.length ? repositoryHeat(bItems[0], workItems, activity, generatedAt) : 0;
      if (bHeat !== aHeat) return bHeat - aHeat;
      return aGroup.localeCompare(bGroup);
    });
}

function roleAssetId(kind) {
  return ROLE_ASSET_IDS[kind] || ROLE_ASSET_IDS.issue;
}

function stateAssetId(lane) {
  return STATE_ASSET_IDS[lane] || STATE_ASSET_IDS.failed;
}

function stationSceneAssetId(workItems) {
  if (workItems.some((item) => item.kind === "workflow_run")) return "scene.terminal.v1";
  if (workItems.some((item) => item.kind === "pull_request")) return "scene.review-bench.v1";
  return "scene.desk.v1";
}

function createAgent(item) {
  const link = document.createElement("a");
  link.className = "world-agent";
  link.dataset.lane = item.lane;
  link.dataset.kind = item.kind;
  link.href = item.url;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.title = item.title;

  const figure = document.createElement("span");
  figure.className = "world-agent-figure";
  figure.setAttribute("aria-hidden", "true");

  const roleId = roleAssetId(item.kind);
  const roleImage = createAssetImage(roleId, "world-role-asset", () => {
    figure.classList.add("has-role-asset");
  });
  const stateId = stateAssetId(item.lane);
  const stateImage = createAssetImage(stateId, "world-state-asset");
  figure.append(roleImage, stateImage);

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

function createStation(repository, workItems, heat) {
  const station = document.createElement("article");
  station.className = "world-station";
  station.dataset.heat = heat.toFixed(2);

  const header = document.createElement("header");
  header.className = "world-station-header";

  const repositoryLink = document.createElement("a");
  repositoryLink.className = "world-station-link";
  repositoryLink.href = repository.url;
  repositoryLink.target = "_blank";
  repositoryLink.rel = "noreferrer";
  const name = document.createElement("strong");
  name.textContent = repository.name;
  const count = document.createElement("span");
  count.textContent = `${workItems.length} agents · heat ${Math.round(heat)}`;
  repositoryLink.append(name, count);
  header.append(repositoryLink);

  const scene = document.createElement("div");
  scene.className = "world-station-scene";
  scene.setAttribute("aria-hidden", "true");
  scene.append(
    createAssetImage(stationSceneAssetId(workItems), "world-scene-asset"),
    createAssetImage("prop.small-pack.v1", "world-prop-asset"),
  );

  const agents = document.createElement("div");
  agents.className = "world-agents";
  agents.setAttribute("aria-label", `${repository.name} agents`);
  for (const item of workItems.slice().sort(compareWorkItems)) {
    agents.append(createAgent(item));
  }

  station.append(header, scene, agents);
  return station;
}

function createZone(group, repositories, workByRepository, workItems, activity, generatedAt) {
  const zone = document.createElement("section");
  zone.className = "world-zone";
  zone.dataset.group = group;
  const isUnclassified = group === UNCLASSIFIED_GROUP;
  if (isUnclassified) zone.classList.add("world-zone-unclassified");

  const floor = createAssetImage("scene.floor.v1", "world-floor-asset");

  const content = document.createElement("div");
  content.className = "world-zone-content";
  const heading = document.createElement("div");
  heading.className = "world-zone-heading";

  const identity = document.createElement("div");
  identity.className = "world-zone-identity";
  identity.append(createAssetImage("scene.sign.v1", "world-sign-asset"));
  const name = document.createElement("strong");
  name.textContent = group;
  identity.append(name);

  const meta = document.createElement("span");
  meta.textContent = isUnclassified
    ? `${repositories.length} stations · classification needed`
    : `${repositories.length} stations · hottest first`;
  heading.append(identity, meta);
  content.append(heading);

  if (isUnclassified) {
    const notice = document.createElement("p");
    notice.className = "world-zone-notice";
    notice.textContent = "未分類: repository Topics に agent-zone-name を追加すると、次回buildで自動分類されます。";
    content.append(notice);
  }

  const stations = document.createElement("div");
  stations.className = "world-stations";
  for (const repository of repositories) {
    const heat = repositoryHeat(repository, workItems, activity, generatedAt);
    stations.append(createStation(repository, workByRepository.get(repository.id) || [], heat));
  }
  content.append(stations);
  zone.append(floor, content);
  return zone;
}

export function renderWorld(repositories, workItems, activity = [], generatedAt = null) {
  const root = document.querySelector("#agent-world-zones");
  const summary = document.querySelector("#agent-world-summary");
  if (!root || !summary) return;

  root.replaceChildren();
  const unclassifiedCount = repositories.filter(
    (repository) => (repository.group || UNCLASSIFIED_GROUP) === UNCLASSIFIED_GROUP,
  ).length;
  summary.textContent = unclassifiedCount > 0
    ? `${workItems.length} agents · ${unclassifiedCount} unclassified repos`
    : `${workItems.length} agents`;

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

  groupedRepositories(repositories, workItems, activity, generatedAt).forEach(([group, items]) => {
    root.append(createZone(group, items, workByRepository, workItems, activity, generatedAt));
  });
}
