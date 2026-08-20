const VALID_LANES = new Set(["waiting", "failed", "done"]);

export function laneFromUrl(value) {
  const url = value instanceof URL ? value : new URL(value, "https://example.invalid/");
  const lane = url.searchParams.get("lane");
  return VALID_LANES.has(lane) ? lane : null;
}

export function urlWithLane(value, lane) {
  const url = value instanceof URL ? new URL(value.href) : new URL(value, "https://example.invalid/");
  if (VALID_LANES.has(lane)) url.searchParams.set("lane", lane);
  else url.searchParams.delete("lane");
  return url;
}

function activateLane(container, lane) {
  if (!VALID_LANES.has(lane)) return false;
  const button = container.querySelector(`button[data-lane="${lane}"]`);
  if (!button) return false;
  button.click();
  return true;
}

function replaceLaneInUrl(lane) {
  const next = urlWithLane(window.location.href, lane);
  window.history.replaceState(null, "", `${next.pathname}${next.search}${next.hash}`);
}

function initialiseOperationsNavigation() {
  const container = document.querySelector("#lane-gates");
  if (!container) return;

  let restoring = false;
  const restore = () => {
    const lane = laneFromUrl(window.location.href);
    if (!lane) return;
    restoring = true;
    activateLane(container, lane);
    restoring = false;
  };

  container.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-lane]");
    if (!button || !container.contains(button) || restoring) return;
    replaceLaneInUrl(button.dataset.lane);
  });

  container.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    const buttons = [...container.querySelectorAll("button[data-lane]")];
    const current = event.target.closest("button[data-lane]");
    const index = buttons.indexOf(current);
    if (index < 0 || buttons.length === 0) return;
    event.preventDefault();
    const delta = event.key === "ArrowRight" ? 1 : -1;
    const next = buttons[(index + delta + buttons.length) % buttons.length];
    next.click();
    next.focus();
  });

  new MutationObserver(restore).observe(container, { childList: true });
  restore();
}

if (typeof document !== "undefined" && typeof window !== "undefined") initialiseOperationsNavigation();
