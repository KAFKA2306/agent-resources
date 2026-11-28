export const STALE_AFTER_MS = 2 * 60 * 60 * 1000;
export const CLOCK_SKEW_TOLERANCE_MS = 5 * 60 * 1000;

export function classifySnapshot(generatedAt, now = Date.now()) {
  const generated = new Date(generatedAt);
  const timestamp = generated.getTime();
  if (Number.isNaN(timestamp)) return { state: "unknown", label: "生成時刻不明", generated: null };
  const age = now - timestamp;
  if (age < -CLOCK_SKEW_TOLERANCE_MS) return { state: "unknown", label: "生成時刻異常", generated };
  if (age > STALE_AFTER_MS) return { state: "stale", label: "古いsnapshot", generated };
  return { state: "fresh", label: "最新snapshot", generated };
}
