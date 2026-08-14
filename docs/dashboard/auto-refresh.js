export const LIVE_REFRESH_INTERVAL_MS = 2 * 60 * 1000;
export const VISIBLE_REFRESH_AFTER_MS = 60 * 1000;
export const MIN_TRIGGER_GAP_MS = 15 * 1000;

let lastTriggerAt = 0;

function triggerLiveRefresh(reason) {
  const now = Date.now();
  if (now - lastTriggerAt < MIN_TRIGGER_GAP_MS) return;
  lastTriggerAt = now;
  window.dispatchEvent(new CustomEvent("dashboard:refresh-live", { detail: { reason } }));
}

window.setInterval(() => triggerLiveRefresh("interval"), LIVE_REFRESH_INTERVAL_MS);
window.addEventListener("focus", () => triggerLiveRefresh("focus"));
window.addEventListener("pageshow", () => triggerLiveRefresh("pageshow"));

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState !== "visible") return;
  if (Date.now() - lastTriggerAt >= VISIBLE_REFRESH_AFTER_MS) triggerLiveRefresh("visibilitychange");
});
