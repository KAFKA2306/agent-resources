const HOUR_MS = 60 * 60 * 1000;
const WINDOW_HOURS = 7 * 24;

export const LANE_PRIORITY = { waiting: 0, failed: 1, working: 2, done: 3 };

function parseTime(value) {
  const time = Date.parse(value);
  return Number.isFinite(time) ? time : null;
}

function recencyScore(value, referenceTime, maxScore) {
  const eventTime = parseTime(value);
  const reference = parseTime(referenceTime);
  if (eventTime === null || reference === null) return 0;
  const ageHours = Math.max(0, (reference - eventTime) / HOUR_MS);
  const remaining = Math.max(0, 1 - Math.min(ageHours, WINDOW_HOURS) / WINDOW_HOURS);
  return maxScore * remaining;
}

export function compareWorkItems(a, b) {
  const priority = (LANE_PRIORITY[a.lane] ?? 99) - (LANE_PRIORITY[b.lane] ?? 99);
  if (priority !== 0) return priority;
  return b.updatedAt.localeCompare(a.updatedAt);
}

export function repositoryHeat(repository, workItems, activity, generatedAt) {
  const items = workItems.filter((item) => item.repositoryId === repository.id);
  const events = activity.filter((item) => item.repositoryId === repository.id);
  const counts = { waiting: 0, failed: 0, working: 0, done: 0 };
  for (const item of items) if (Object.hasOwn(counts, item.lane)) counts[item.lane] += 1;
  const latestActivity = events.reduce((latest, item) => (!latest || item.occurredAt > latest ? item.occurredAt : latest), null);
  const activityVolume = Math.min(40, Math.log2(events.length + 1) * 10);
  const activityRecency = latestActivity ? recencyScore(latestActivity, generatedAt, 30) : 0;
  const repositoryRecency = recencyScore(repository.updatedAt, generatedAt, 10);
  return counts.failed * 300 + counts.waiting * 250 + counts.working * 50 + counts.done * 2 + activityVolume + activityRecency + repositoryRecency;
}

export function rankRepositories(repositories, workItems, activity, generatedAt) {
  return repositories.slice().sort((a, b) => {
    const heatDelta = repositoryHeat(b, workItems, activity, generatedAt) - repositoryHeat(a, workItems, activity, generatedAt);
    if (heatDelta !== 0) return heatDelta;
    const updatedDelta = b.updatedAt.localeCompare(a.updatedAt);
    if (updatedDelta !== 0) return updatedDelta;
    return a.name.localeCompare(b.name);
  });
}
