const feed = document.querySelector("#activity-feed");

const ACTIVITY_KIND_BY_LABEL = new Map([
  ["Issue", "issue"],
  ["Pull Request", "pull_request"],
  ["Workflow Run", "workflow_run"],
]);

const ACTIVITY_ICON_BY_KIND = {
  issue: "ks-issue",
  pull_request: "ks-pull-request",
  workflow_run: "ks-workflow",
};

const SVG_NS = "http://www.w3.org/2000/svg";
const ICON_SPRITE = "./assets/kafka-signal-icons.svg";

function createIcon(symbol) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.classList.add("activity-timeline-icon");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  const use = document.createElementNS(SVG_NS, "use");
  use.setAttribute("href", `${ICON_SPRITE}#${symbol}`);
  svg.append(use);
  return svg;
}

function enhanceActivityItem(item) {
  if (item.dataset.timelineEnhanced === "true") return true;
  const label = item.querySelector(".activity-kind")?.textContent?.trim();
  const kind = ACTIVITY_KIND_BY_LABEL.get(label);
  const symbol = kind ? ACTIVITY_ICON_BY_KIND[kind] : null;
  if (!kind || !symbol) return false;

  const marker = document.createElement("span");
  marker.className = "activity-timeline-marker";
  marker.setAttribute("aria-hidden", "true");
  marker.append(createIcon(symbol));

  item.dataset.activityKind = kind;
  item.dataset.timelineEnhanced = "true";
  item.prepend(marker);
  return true;
}

function enhanceActivityFeed() {
  if (!feed) return;
  const items = [...feed.querySelectorAll(".activity-item")];
  const enhanced = items.filter(enhanceActivityItem).length;
  feed.classList.toggle("activity-timeline", enhanced > 0);
}

if (feed) {
  new MutationObserver(enhanceActivityFeed).observe(feed, { childList: true });
  enhanceActivityFeed();
}
