const assetVersion = encodeURIComponent(new URL(import.meta.url).searchParams.get("v") || Date.now().toString());
const { compareWorkItems, rankRepositories, repositoryHeat } = await import(`./ranking.js?v=${assetVersion}`);

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
    const group = repository.group || "unclassified";
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push(repository);
  }
  return [...groups.entries()]
    .map(([group, items]) => [group, rankRepositories(items, workItems, activity, generatedAt)])
    .sort(([aGroup, aItems], [bGroup, bItems]) => {
      if (aGroup === "unclassified" && bGroup !== "unclassified") return 1;
      if (aGroup !== "unclassified" && bGroup === "unclassified") return -1;
      const aHeat = aItems.length ? repositoryHeat(aItems[0], workItems, activity, generatedAt) : 0;
      const bHeat = bItems.length ? repositoryHeat(bItems[0], workItems, activity, generatedAt) : 0;
      return bHeat - aHeat;
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

function createPublicSurfaceLinks(repository) {
  const links = Array.isArray(repository.publicLinks) ? repository.publicLinks : [];
  const safeLinks = links.filter(
    (link) =>
      link &&
      (link.kind === "front" || link.kind === "pages") &&
      typeof link.url === "string" &&
      link.url.startsWith("https://"),
  );
  if (!safeLinks.length) return null;

  const actions = document.createElement("div");
  actions.className = "world-station-actions";
  for (const link of safeLinks) {
    const anchor = document.createElement("a");
    anchor.className = `world-surface-link world-surface-link-${link.kind}`;
    anchor.href = link.url;
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
    anchor.textContent = link.kind === "pages" ? "PAGES ↗" : "FRONT ↗";
    anchor.title = `${repository.name} ${link.kind === "pages" ? "GitHub Pages" : "frontend"} を開く`;
    actions.append(anchor);
  }
  return actions;
}

function createStation(repository, workItems, heat) {
  const station = document.createElement("article");
  station.className = "world-station";
  station.dataset.heat = heat.toFixed(2);

  const scene = document.createElement("div");
  scene.className = "world-station-scene";
  scene.setAttribute("aria-hidden", "true");
  scene.append(
    createAssetImage(stationSceneAssetId(workItems), "world-scene-asset"),
    createAssetImage("prop.small-pack.v1", "world-prop-asset"),
  );

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

  const agents = document.createElement("div");
  agents.className = "world-agents";
  agents.setAttribute("aria-label", `${repository.name} agents`);
  for (const item of workItems.slice().sort(compareWorkItems)) {
    agents.append(createAgent(item));
  }

  station.append(repositoryLink, scene, agents);
  const publicSurfaceLinks = createPublicSurfaceLinks(repository);
  if (publicSurfaceLinks) station.insertBefore(publicSurfaceLinks, scene);
  return station;
}

function createZone(group, repositories, workByRepository, workItems, activity, generatedAt) {
  const isUnclassified = group === "unclassified";
  const zone = document.createElement("section");
  zone.className = isUnclassified ? "world-zone world-zone-unclassified" : "world-zone";

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
    ? `${repositories.length} stations · agent-zone-* topic未設定`
    : `${repositories.length} stations · hottest first`;
  heading.append(identity, meta);

  const stations = document.createElement("div");
  stations.className = "world-stations";
  for (const repository of repositories) {
    const heat = repositoryHeat(repository, workItems, activity, generatedAt);
    stations.append(createStation(repository, workByRepository.get(repository.id) || [], heat));
  }

  if (isUnclassified) {
    const details = document.createElement("details");
    details.className = "world-unclassified-details";
    details.open = true;
    const summary = document.createElement("summary");
    summary.textContent = `未分類 ${repositories.length} repositories（通常表示）`;
    details.append(summary, stations);
    content.append(heading, details);
  } else {
    content.append(heading, stations);
  }
  zone.append(floor, content);
  return zone;
}

export function renderWorld(repositories, workItems, activity = [], generatedAt = null) {
  const root = document.querySelector("#agent-world-zones");
  const summary = document.querySelector("#agent-world-summary");
  if (!root || !summary) return;

  root.replaceChildren();
  const classifiedRepositories = repositories.filter(
    (repository) => (repository.group || "unclassified") !== "unclassified",
  ).length;
  const unclassifiedRepositories = repositories.length - classifiedRepositories;
  summary.textContent = `${workItems.length} agents · ${classifiedRepositories}/${repositories.length} zoned · ${unclassifiedRepositories} unclassified`;

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
