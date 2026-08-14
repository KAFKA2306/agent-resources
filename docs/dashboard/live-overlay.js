export const LIVE_MAX_AGE_MS = 150 * 1000;
export const LIVE_CLOCK_SKEW_TOLERANCE_MS = 5 * 60 * 1000;

export function classifyLive(fetchedAt, now = Date.now()) {
  const fetched = new Date(fetchedAt);
  const timestamp = fetched.getTime();
  if (Number.isNaN(timestamp)) return { state: "failed", label: "SNAPSHOT FALLBACK", fetched: null };
  const age = now - timestamp;
  if (age < -LIVE_CLOCK_SKEW_TOLERANCE_MS) return { state: "stale", label: "STALE", fetched };
  if (age > LIVE_MAX_AGE_MS) return { state: "stale", label: "STALE", fetched };
  return { state: "live", label: "LIVE", fetched };
}

export function mergeLiveSnapshot(baseline, live) {
  if (!baseline || typeof baseline !== "object") throw new TypeError("baseline snapshot is required");
  if (!live || live.scope !== "public" || !Array.isArray(live.repositories) || !Array.isArray(live.workItems) || !Array.isArray(live.activity)) {
    throw new TypeError("live payload is invalid or not public-only");
  }
  const repositoryIds = new Set(live.repositories.map((repo) => repo.id));
  if (live.repositories.some((repo) => repo.visibility !== "public" || repo.archived === true)) {
    throw new TypeError("live payload crossed the public repository boundary");
  }
  if (live.workItems.some((item) => !repositoryIds.has(item.repositoryId)) || live.activity.some((item) => !repositoryIds.has(item.repositoryId))) {
    throw new TypeError("live payload references a non-public repository");
  }
  return {
    ...baseline,
    repositories: live.repositories,
    workItems: live.workItems,
    activity: live.activity,
    summary: {
      ...(baseline.summary || {}),
      repositoryCount: live.repositories.length,
      workItemCount: live.workItems.length,
      activityCount: live.activity.length,
    },
    liveFetchedAt: live.fetchedAt,
    liveSchemaVersion: live.schemaVersion,
    liveRequestBudget: live.requestBudget || null,
  };
}
