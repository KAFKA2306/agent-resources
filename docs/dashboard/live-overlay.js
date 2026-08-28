export const LIVE_MAX_AGE_MS = 5 * 60 * 1000;

function parseTime(value) {
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function classifyLive(fetchedAt, nowMs = Date.now()) {
  const fetchedMs = parseTime(fetchedAt);
  if (fetchedMs === null) return { label: "SNAPSHOT FALLBACK", state: "failed", ageMs: null, isFresh: false };
  const ageMs = Math.max(0, nowMs - fetchedMs);
  return ageMs <= LIVE_MAX_AGE_MS
    ? { label: "LIVE", state: "fresh", ageMs, isFresh: true }
    : { label: "STALE", state: "stale", ageMs, isFresh: false };
}

export function mergeLiveSnapshot(baseline, live) {
  if (!live || live.scope !== "public") throw new Error("live payload must be public-only");
  if (!Array.isArray(live.repositories) || !Array.isArray(live.workItems) || !Array.isArray(live.activity)) {
    throw new Error("live payload is incomplete");
  }
  const baselineRepositoriesById = new Map(
    (baseline.repositories || []).map((repository) => [repository.id, repository]),
  );
  const repositories = live.repositories.map((repository) => {
    const baselineRepository = baselineRepositoriesById.get(repository.id);
    if (!Array.isArray(baselineRepository?.publicLinks)) return repository;
    return { ...repository, publicLinks: baselineRepository.publicLinks };
  });
  const repositoryIds = new Set();
  for (const repository of repositories) {
    if (repository.visibility !== "public" || repository.archived === true) {
      throw new Error("live payload crossed the public repository boundary");
    }
    repositoryIds.add(repository.id);
  }
  for (const item of live.workItems) {
    if (!repositoryIds.has(item.repositoryId)) throw new Error("live work item references a non-public repository");
  }
  for (const item of live.activity) {
    if (!repositoryIds.has(item.repositoryId)) throw new Error("live activity references a non-public repository");
  }

  const workItemsById = new Map();
  for (const item of baseline.workItems || []) {
    if (item.kind === "workflow_run" && repositoryIds.has(item.repositoryId)) workItemsById.set(item.id, item);
  }
  for (const item of live.workItems) workItemsById.set(item.id, item);
  const workItems = [...workItemsById.values()].sort((a, b) =>
    a.repositoryId.localeCompare(b.repositoryId) || a.kind.localeCompare(b.kind) || a.number - b.number,
  );

  const activityById = new Map();
  for (const item of baseline.activity || []) {
    if (item.kind === "workflow_run" && repositoryIds.has(item.repositoryId)) activityById.set(item.id, item);
  }
  for (const item of live.activity) activityById.set(item.id, item);
  const activity = [...activityById.values()].sort(
    (a, b) => b.occurredAt.localeCompare(a.occurredAt) || b.id.localeCompare(a.id),
  );

  return {
    ...baseline,
    generatedAt: baseline.generatedAt,
    liveFetchedAt: live.fetchedAt,
    liveSource: live.source || "github-rest",
    liveRequestBudget: live.requestBudget || null,
    repositories,
    workItems,
    activity,
    summary: {
      ...(baseline.summary || {}),
      repositoryCount: repositories.length,
      workItemCount: workItems.length,
      activityCount: activity.length,
    },
  };
}

export async function fetchLivePayload(endpoint, fetchImpl = globalThis.fetch) {
  if (!endpoint) throw new Error("live endpoint is not configured");
  const response = await fetchImpl(endpoint, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`live endpoint returned HTTP ${response.status}`);
  return response.json();
}
