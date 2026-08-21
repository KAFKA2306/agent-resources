const REPOSITORY_OPERATIONS_SOURCES = [
  "./repository-operations.json",
  "https://kafka2306.github.io/agent-resources/dashboard/repository-operations.json",
];
const ZONE_WORKFLOW_URL = "https://github.com/KAFKA2306/agent-resources/actions/workflows/topic-bootstrap-67.yml";

function formatTimestamp(value) {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return "invalid timestamp";
  return new Intl.DateTimeFormat("ja-JP", {
    dateStyle: "medium",
    timeStyle: "medium",
    timeZone: "Asia/Tokyo",
  }).format(new Date(timestamp));
}

export function summarizeRepositoryOperations(payload) {
  if (!payload || typeof payload !== "object") throw new TypeError("repository operations payload must be an object");
  if (!payload.generatedAt) throw new TypeError("repository operations payload is missing generatedAt");
  if (!Array.isArray(payload.repositories)) throw new TypeError("repository operations payload is missing repositories");

  const classified = payload.repositories.filter((repository) => Boolean(repository?.classification?.domain)).length;
  return {
    generatedAt: payload.generatedAt,
    generatedLabel: formatTimestamp(payload.generatedAt),
    repositoryCount: payload.repositories.length,
    classifiedCount: classified,
    unclassifiedCount: payload.repositories.length - classified,
  };
}

export function renderRepositoryOperationsSummary(payload, documentRef = document) {
  const generatedAt = documentRef.getElementById("operations-generated-at");
  const summary = documentRef.getElementById("operations-summary");
  const zoneAction = documentRef.getElementById("operations-zone-action");
  if (!generatedAt || !summary) return;

  const state = summarizeRepositoryOperations(payload);
  generatedAt.dateTime = state.generatedAt;
  generatedAt.textContent = `Operations snapshot: ${state.generatedLabel}`;
  summary.textContent = `Operations: ${state.repositoryCount} repos · ${state.classifiedCount} classified · ${state.unclassifiedCount} unclassified`;
  if (zoneAction) zoneAction.href = ZONE_WORKFLOW_URL;
}

export async function loadRepositoryOperations({ fetchImpl = fetch, documentRef = document } = {}) {
  const generatedAt = documentRef.getElementById("operations-generated-at");
  const summary = documentRef.getElementById("operations-summary");
  let lastError = null;

  for (const source of REPOSITORY_OPERATIONS_SOURCES) {
    try {
      const response = await fetchImpl(source, { cache: "no-store" });
      if (!response.ok) throw new Error(`repository operations HTTP ${response.status}`);
      renderRepositoryOperationsSummary(await response.json(), documentRef);
      return;
    } catch (error) {
      lastError = error;
    }
  }

  if (generatedAt) generatedAt.textContent = "Operations snapshot: unavailable";
  if (summary) summary.textContent = "Operations: unavailable";
  console.warn("Repository operations snapshot unavailable", lastError);
}

if (typeof document !== "undefined") {
  void loadRepositoryOperations();
}
