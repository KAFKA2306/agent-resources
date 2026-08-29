const assetVersion = encodeURIComponent(new URL(import.meta.url).searchParams.get("v") || Date.now().toString());
const { compareWorkItems, rankRepositories, repositoryHeat } = await import(`./ranking.js?v=${assetVersion}`);

const ASSET_ROOT = "./assets/agent-world";
const WORK_ITEM_COLLAPSE_THRESHOLD = 4;

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

  const roleImage = createAssetImage(roleAssetId(item.kind), "world-role-asset", () => {
    figure.classList.add("has-role-asset");
  });
  const stateImage = createAssetImage(stateAssetId(item.lane), "world-state-asset");
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

function createAgentList(items, label) {
  const agents = document.createElement("div");
  agents.className = "world-agents";
  agents.setAttribute("aria-label", label);
  for (const item of items.slice().sort(compareWorkItems)) {
    agents.append(createAgent(item));
  }
  return agents;
}

function issuePullRequestSummary(items) {
  const issueCount = items.filter((item) => item.kind === "issue").length;
  const pullRequestCount = items.filter((item) => item.kind === "pull_request").length;
  return [issueCount ? `ISSUE ${issueCount}` : "", pullRequestCount ? `PR ${pullRequestCount}` : ""]
    .filter(Boolean)
    .join(" · ");
}

function createWorkItemView(repository, workItems) {
  const issuePullRequests = workItems.filter(
    (item) => item.kind === "issue" || item.kind === "pull_request",
  );
  if (issuePullRequests.length <= WORK_ITEM_COLLAPSE_THRESHOLD) {
    return createAgentList(workItems, `${repository.name} work items`);
  }

  const container = document.createElement("div");
  container.className = "world-work-items";
  const alwaysVisible = workItems.filter(
    (item) => item.kind !== "issue" && item.kind !== "pull_request",
  );
  if (alwaysVisible.length) {
    container.append(createAgentList(alwaysVisible, `${repository.name} workflow runs`));
  }

  const details = document.createElement("details");
  details.className = "world-work-details";
  const summary = document.createElement("summary");
  summary.textContent = issuePullRequestSummary(issuePullRequests);
  details.append(
    summary,
    createAgentList(issuePullRequests, `${repository.name} issues and pull requests`),
  );
  container.append(details);
  return container;
}

function createSurfaceIcon(publicUrl) {
  try {
    const base = new URL(publicUrl);
    if (!base.pathname.endsWith("/")) base.pathname += "/";
    const image = document.createElement("img");
    image.className = "world-surface-icon";
    image.alt = "";
    image.loading = "lazy";
    image.decoding = "async";
    image.referrerPolicy = "no-referrer";
    image.setAttribute("aria-hidden", "true");
    image.addEventListener(
      "error",
      () => {
        image.hidden = true;
      },
      { once: true },
    );
    image.src = new URL("favicon.ico", base).href;
    return image;
  } catch {
    return null;
  }
}

export function createPublicSurfaceLinks(repository) {
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
    const icon = createSurfaceIcon(link.url);
    if (icon) anchor.prepend(icon);
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
  count.textContent = `作業項目 ${workItems.length}件 · heat ${Math.round(heat)}`;
  repositoryLink.append(name, count);

  const agents = createWorkItemView(repository, workItems);

  station.append(repositoryLink, scene, agents);
  const publicSurfaceLinks = createPublicSurfaceLinks(repository);
  if (publicSurfaceLinks) station.insertBefore(publicSurfaceLinks, scene);
  return station;
}

export function renderWorld(repositories, workItems, activity = [], generatedAt = null) {
  const root = document.querySelector("#agent-world-zones");
  const summary = document.querySelector("#agent-world-summary");
  if (!root || !summary) return;

  root.replaceChildren();
  summary.textContent = `作業項目 ${workItems.length}件 · ${repositories.length} repositories`;

  if (repositories.length === 0) {
    const empty = document.createElement("p");
    empty.className = "world-empty muted";
    empty.textContent = "表示できるrepositoryは0件です。";
    root.append(empty);
    return;
  }

  const workByRepository = new Map();
  for (const item of workItems) {
    if (!workByRepository.has(item.repositoryId)) workByRepository.set(item.repositoryId, []);
    workByRepository.get(item.repositoryId).push(item);
  }

  const stations = document.createElement("div");
  stations.className = "world-stations";
  for (const repository of rankRepositories(repositories, workItems, activity, generatedAt)) {
    const heat = repositoryHeat(repository, workItems, activity, generatedAt);
    stations.append(createStation(repository, workByRepository.get(repository.id) || [], heat));
  }
  root.append(stations);
}
