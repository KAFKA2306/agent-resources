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

const SVG_NS = "http://www.w3.org/2000/svg";

function repositoryLane(items) {
  if (items.some((item) => item.lane === "failed")) return "failed";
  if (items.some((item) => item.lane === "waiting")) return "waiting";
  if (items.some((item) => item.lane === "working")) return "working";
  if (items.some((item) => item.lane === "done")) return "done";
  return "idle";
}

function repositorySeed(value) {
  let hash = 2166136261;
  for (const char of String(value || "")) {
    hash ^= char.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return Math.abs(hash >>> 0);
}

function createSvg(tag, attributes = {}) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, String(value));
  return node;
}

export function renderWorld(repositories, workItems, activity = [], generatedAt = null) {
  const root = document.querySelector("#agent-world-zones");
  const summary = document.querySelector("#agent-world-summary");
  if (!root || !summary) return;

  root.replaceChildren();

  if (repositories.length === 0) {
    summary.textContent = "0 NODES";
    const empty = document.createElement("p");
    empty.className = "world-empty muted";
    empty.textContent = "NO SIGNAL";
    root.append(empty);
    return;
  }

  const workByRepository = new Map();
  for (const item of workItems) {
    if (!workByRepository.has(item.repositoryId)) workByRepository.set(item.repositoryId, []);
    workByRepository.get(item.repositoryId).push(item);
  }

  const ranked = rankRepositories(repositories, workItems, activity, generatedAt);
  const heatById = new Map(
    ranked.map((repository) => [
      repository.id,
      repositoryHeat(repository, workItems, activity, generatedAt),
    ]),
  );
  const maxHeat = Math.max(1, ...heatById.values());
  const activeCount = ranked.filter((repository) => (workByRepository.get(repository.id) || []).length > 0).length;
  summary.textContent = `${repositories.length} NODES · ${activeCount} ACTIVE`;

  const shell = document.createElement("div");
  shell.className = "repository-constellation-shell";

  const svg = createSvg("svg", {
    viewBox: "0 0 1000 610",
    role: "img",
    "aria-label": `${repositories.length} public repositories plotted as a factory constellation`,
    preserveAspectRatio: "xMidYMid meet",
  });
  svg.classList.add("repository-constellation");

  const background = createSvg("g");
  background.classList.add("constellation-grid");
  for (const radius of [92, 170, 250, 330, 410]) {
    background.append(createSvg("circle", { cx: 500, cy: 300, r: radius }));
  }
  background.append(
    createSvg("line", { x1: 55, y1: 300, x2: 945, y2: 300 }),
    createSvg("line", { x1: 500, y1: 40, x2: 500, y2: 560 }),
  );
  svg.append(background);

  const center = createSvg("g");
  center.classList.add("constellation-core");
  center.append(
    createSvg("circle", { cx: 500, cy: 300, r: 34 }),
    createSvg("circle", { cx: 500, cy: 300, r: 54 }),
  );
  const coreText = createSvg("text", { x: 500, y: 305, "text-anchor": "middle" });
  coreText.textContent = "CORE";
  center.append(coreText);
  svg.append(center);

  const points = [];
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  ranked.forEach((repository, index) => {
    const items = workByRepository.get(repository.id) || [];
    const heat = heatById.get(repository.id) || 0;
    const heatRatio = Math.min(1, heat / maxHeat);
    const seed = repositorySeed(repository.id || repository.name);
    const jitter = ((seed % 997) / 997 - 0.5) * 0.38;
    const progress = ranked.length <= 1 ? 0 : index / (ranked.length - 1);
    const radius = 100 + Math.sqrt(progress) * 335 - heatRatio * 58;
    const angle = index * goldenAngle + jitter;
    const x = 500 + Math.cos(angle) * radius * 1.08;
    const y = 300 + Math.sin(angle) * radius * 0.67;
    points.push({
      repository,
      items,
      heat,
      heatRatio,
      lane: repositoryLane(items),
      x,
      y,
      index,
    });
  });

  const edgeLayer = createSvg("g");
  edgeLayer.classList.add("constellation-edges");
  for (const point of points.filter((point) => point.items.length > 0)) {
    const edge = createSvg("line", {
      x1: 500,
      y1: 300,
      x2: point.x.toFixed(1),
      y2: point.y.toFixed(1),
    });
    edge.classList.add("constellation-edge", `is-${point.lane}`);
    edge.style.setProperty("--edge-delay", `${(point.index * 0.07).toFixed(2)}s`);
    edgeLayer.append(edge);
  }
  svg.append(edgeLayer);

  const nodeLayer = createSvg("g");
  nodeLayer.classList.add("constellation-nodes");
  for (const point of points) {
    const { repository, items, heat, heatRatio, lane, x, y, index } = point;
    const anchor = createSvg("a", {
      href: repository.url,
      target: "_blank",
      rel: "noopener noreferrer",
      tabindex: "0",
    });
    anchor.classList.add("constellation-node", `is-${lane}`);
    if (Array.isArray(repository.publicLinks) && repository.publicLinks.length) {
      anchor.classList.add("has-surface");
    }

    const nodeRadius = Math.min(11, 3.2 + heatRatio * 5.2 + Math.sqrt(items.length) * 0.85);
    const halo = createSvg("circle", {
      cx: x.toFixed(1),
      cy: y.toFixed(1),
      r: (nodeRadius + (items.length ? 5 : 2)).toFixed(1),
    });
    halo.classList.add("constellation-node-halo");
    const dot = createSvg("circle", {
      cx: x.toFixed(1),
      cy: y.toFixed(1),
      r: nodeRadius.toFixed(1),
    });
    dot.classList.add("constellation-node-dot");

    const title = createSvg("title");
    title.textContent = `${repository.name} · ${items.length} work · heat ${Math.round(heat)}`;
    anchor.append(title, halo, dot);

    if (index < 16 || items.length > 0 && index < 28) {
      const label = createSvg("text", {
        x: (x + (x >= 500 ? nodeRadius + 6 : -nodeRadius - 6)).toFixed(1),
        y: (y + 3).toFixed(1),
        "text-anchor": x >= 500 ? "start" : "end",
      });
      label.classList.add("constellation-node-label");
      label.textContent = repository.name;
      anchor.append(label);
    }

    nodeLayer.append(anchor);
  }
  svg.append(nodeLayer);

  const legend = document.createElement("div");
  legend.className = "constellation-legend";
  for (const [lane, label] of [
    ["working", "LIVE"],
    ["waiting", "WAIT"],
    ["failed", "FAIL"],
    ["idle", "IDLE"],
  ]) {
    const item = document.createElement("span");
    item.dataset.lane = lane;
    item.textContent = label;
    legend.append(item);
  }

  shell.append(svg, legend);
  root.append(shell);
}
