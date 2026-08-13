const AUTO_REFRESH_MS = 5 * 60 * 1000;
const VISIBLE_REFRESH_AFTER_MS = 60 * 1000;
let lastRefreshAt = Date.now();

function refreshPage() {
  lastRefreshAt = Date.now();
  window.location.reload();
}

window.setInterval(refreshPage, AUTO_REFRESH_MS);

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState !== "visible") return;
  if (Date.now() - lastRefreshAt >= VISIBLE_REFRESH_AFTER_MS) refreshPage();
});
