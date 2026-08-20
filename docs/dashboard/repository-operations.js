function formatTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "取得時刻不明";
  return new Intl.DateTimeFormat("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function isStale(value, hours = 6) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return true;
  return Date.now() - date.getTime() > hours * 60 * 60 * 1000;
}

function summaryCard(label, value) {
  const card = document.createElement("div");
  card.className = "repository-operations-stat";
  const strong = document.createElement("strong");
  strong.textContent = String(value ?? 0);
  const span = document.createElement("span");
  span.textContent = label;
  card.append(strong, span);
  return card;
}

export function renderRepositoryOperations(operations) {
  const section = document.querySelector("#repository-operations");
  const summary = document.querySelector("#repository-operations-summary");
  const branches = document.querySelector("#repository-operations-branches");
  const meta = document.querySelector("#repository-operations-meta");
  if (!section || !summary || !branches || !meta) return;

  if (
    !operations ||
    operations.scope !== "public-nonarchived-owned-repositories" ||
    !operations.summary ||
    !Array.isArray(operations.repositories) ||
    !Array.isArray(operations.branches)
  ) {
    section.hidden = true;
    return;
  }

  const stale = isStale(operations.collectedAt);
  section.dataset.stale = stale ? "true" : "false";
  meta.textContent = `${stale ? "STALE · " : ""}Snapshot: ${formatTime(operations.collectedAt)}`;

  summary.replaceChildren(
    summaryCard("classified", operations.summary.classifiedCount),
    summaryCard("unclassified", operations.summary.unclassifiedCount),
    summaryCard("branch candidates", operations.summary.candidateCount),
    summaryCard("confirmed", operations.summary.confirmedCount),
    summaryCard("deleted", operations.summary.deletedCount),
    summaryCard("blocked", operations.summary.blockedCount),
  );

  branches.replaceChildren();
  const active = operations.branches.filter((row) => row.status !== "deleted").slice(0, 30);
  if (active.length === 0) {
    const empty = document.createElement("p");
    empty.className = "muted repository-operations-empty";
    empty.textContent = "branch hygieneの未解決項目はありません。";
    branches.append(empty);
  } else {
    for (const row of active) {
      const item = document.createElement("div");
      item.className = "repository-operation-row";
      item.dataset.status = row.status;

      const identity = document.createElement("div");
      const repo = document.createElement("strong");
      repo.textContent = row.repository;
      const branch = document.createElement("code");
      branch.textContent = row.branch;
      identity.append(repo, branch);

      const state = document.createElement("div");
      const status = document.createElement("strong");
      status.textContent = row.status;
      const reason = document.createElement("span");
      reason.className = "muted";
      reason.textContent = row.reason;
      state.append(status, reason);
      item.append(identity, state);
      branches.append(item);
    }
  }

  section.hidden = false;
}

async function loadRepositoryOperations() {
  try {
    const response = await fetch("./dashboard.json", { cache: "no-store" });
    if (!response.ok) return;
    const snapshot = await response.json();
    renderRepositoryOperations(snapshot.repositoryOperations);
  } catch (error) {
    console.warn("Repository operations snapshot unavailable", error);
  }
}

if (typeof document !== "undefined" && typeof fetch === "function") {
  loadRepositoryOperations();
}
