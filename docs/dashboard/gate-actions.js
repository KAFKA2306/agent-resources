const gateDetail = document.querySelector("#gate-detail");
const laneGates = document.querySelector("#lane-gates");
const operationsSummary = document.querySelector(".operations-summary");

export const PRIMARY_LANE_ORDER = ["failed", "waiting"];

function ensurePrimaryAction() {
  if (!operationsSummary) return null;
  let primary = document.querySelector("#primary-action");
  if (primary) return primary;

  primary = document.createElement("section");
  primary.id = "primary-action";
  primary.className = "gate-detail primary-action";
  primary.setAttribute("aria-live", "polite");
  primary.hidden = true;
  operationsSummary.parentElement?.insertBefore(primary, operationsSummary);
  return primary;
}

export function enhanceGateItems(root = gateDetail) {
  if (!root) return;
  for (const row of root.querySelectorAll(".gate-item")) {
    if (row.querySelector(".gate-item-owner")) continue;
    const canonicalLink = row.querySelector(".gate-item-link");
    if (!canonicalLink) continue;

    const separator = " · ";
    const [repositoryName] = canonicalLink.textContent.split(separator, 1);

    const owner = document.createElement("span");
    owner.className = "gate-item-meta gate-item-owner";
    owner.textContent = `Owner repository: ${repositoryName || "unknown"}`;

    const action = document.createElement("a");
    action.className = "gate-item-action";
    action.href = canonicalLink.href;
    action.target = "_blank";
    action.rel = "noreferrer";
    action.textContent = "次の行動: 対応先を開く";

    canonicalLink.parentElement?.append(owner, action);
  }
}

function promotePrimaryAction() {
  if (!gateDetail) return;
  enhanceGateItems(gateDetail);
  const firstItem = gateDetail.querySelector(".gate-item");
  const primary = ensurePrimaryAction();
  if (!primary) return;

  if (!firstItem) {
    primary.hidden = true;
    primary.replaceChildren();
    return;
  }

  const heading = document.createElement("h3");
  heading.textContent = "最優先の対応";
  primary.replaceChildren(heading, firstItem.cloneNode(true));
  primary.hidden = false;
  gateDetail.hidden = true;
}

function selectedLaneFromUrl() {
  const lane = new URL(window.location.href).searchParams.get("lane");
  return lane && laneGates?.querySelector(`button[data-lane="${lane}"]`) ? lane : null;
}

function restoreUrl(href) {
  const original = new URL(href);
  window.history.replaceState(null, "", `${original.pathname}${original.search}${original.hash}`);
}

function selectPrimaryGate() {
  if (!laneGates || !gateDetail) return;
  if (selectedLaneFromUrl()) return;

  const selected = PRIMARY_LANE_ORDER
    .map((lane) => laneGates.querySelector(`button[data-lane="${lane}"]`))
    .find((button) => button && Number(button.querySelector("strong")?.textContent || 0) > 0);
  if (!selected) {
    const primary = ensurePrimaryAction();
    if (primary) {
      primary.hidden = true;
      primary.replaceChildren();
    }
    return;
  }

  const originalHref = window.location.href;
  selected.click();
  promotePrimaryAction();
  restoreUrl(originalHref);
}

if (gateDetail) {
  new MutationObserver(() => enhanceGateItems()).observe(gateDetail, { childList: true, subtree: true });
  enhanceGateItems();
}

if (laneGates) {
  new MutationObserver(() => selectPrimaryGate()).observe(laneGates, { childList: true });
  selectPrimaryGate();
}
