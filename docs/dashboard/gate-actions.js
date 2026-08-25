const gateDetail = document.querySelector("#gate-detail");

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
    action.textContent = "対応先を開く";

    canonicalLink.parentElement?.append(owner, action);
  }
}

if (gateDetail) {
  new MutationObserver(() => enhanceGateItems()).observe(gateDetail, { childList: true, subtree: true });
  enhanceGateItems();
}
