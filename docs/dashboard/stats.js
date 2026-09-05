const STAT_SERIES = [
  { key: "commits", label: "Commit" },
  { key: "prsMerged", label: "Merged PR" },
  { key: "issuesClosed", label: "Closed Issue" },
];

const VIEW_CONFIG = {
  monthly: {
    title: "月次推移",
    rowsKey: "monthly",
    sortKey: "month",
    ariaLabel: "GitHub月次活動",
    partialNote: "* は当月途中集計。",
  },
  weekly: {
    title: "週次推移",
    rowsKey: "weekly",
    sortKey: "weekStart",
    ariaLabel: "GitHub週次活動",
    partialNote: "* は当週途中集計。",
  },
};

let currentStats = null;

function statCard(label, value, note) {
  const card = document.createElement("div");
  card.className = "stat-card";
  const name = document.createElement("span");
  name.textContent = label;
  const count = document.createElement("strong");
  count.textContent = Number.isInteger(value) ? value.toLocaleString("ja-JP") : "—";
  const detail = document.createElement("small");
  detail.textContent = note;
  card.append(name, count, detail);
  return card;
}

function shortDate(value) {
  const parts = value.split("-").map(Number);
  if (parts.length !== 3 || parts.some((part) => !Number.isInteger(part))) return value;
  return { year: parts[0], month: parts[1], day: parts[2] };
}

function weekLabel(row) {
  const start = shortDate(row.weekStart);
  const end = shortDate(row.weekEnd);
  if (typeof start === "string" || typeof end === "string") return `${row.weekStart}–${row.weekEnd}`;
  if (start.year === end.year) {
    return `${start.year} ${start.month}/${start.day}–${end.month}/${end.day}`;
  }
  return `${start.year}/${start.month}/${start.day}–${end.year}/${end.month}/${end.day}`;
}

function rowLabel(view, row) {
  return view === "weekly" ? weekLabel(row) : row.month;
}

function requestedView() {
  return new URLSearchParams(window.location.search).get("stats") === "weekly" ? "weekly" : "monthly";
}

function selectView(view) {
  const url = new URL(window.location.href);
  if (view === "weekly") {
    url.searchParams.set("stats", "weekly");
  } else {
    url.searchParams.delete("stats");
  }
  window.history.replaceState({}, "", url);
  renderStats(currentStats);
}

function configureViewControls(view, stats) {
  for (const button of document.querySelectorAll("[data-stats-view]")) {
    const buttonView = button.dataset.statsView;
    button.setAttribute("aria-pressed", String(buttonView === view));
    const rows = VIEW_CONFIG[buttonView] ? stats?.[VIEW_CONFIG[buttonView].rowsKey] : null;
    button.disabled = !Array.isArray(rows) || rows.length === 0;
    button.onclick = () => selectView(buttonView);
  }
}

export function renderStats(stats) {
  currentStats = stats;
  const statsSummary = document.querySelector("#stats-summary");
  const statsMonthly = document.querySelector("#stats-monthly");
  const statsNote = document.querySelector("#stats-note");
  const statsScope = document.querySelector("#stats-scope");
  const statsLegend = document.querySelector("#stats-legend");
  const statsTitle = document.querySelector("#github-stats-title");
  if (!statsSummary || !statsMonthly || !statsNote || !statsScope) return;

  const view = requestedView();
  const config = VIEW_CONFIG[view];
  configureViewControls(view, stats);
  statsSummary.replaceChildren();
  statsMonthly.replaceChildren();
  statsScope.textContent = "public only";
  statsMonthly.dataset.view = view;
  statsMonthly.setAttribute("aria-label", config.ariaLabel);
  if (statsTitle) statsTitle.textContent = config.title;

  if (!stats || stats.scope !== "public") {
    if (statsLegend) statsLegend.hidden = true;
    statsSummary.append(statCard("公開統計", null, "未取得"));
    statsNote.textContent = "公開GitHub統計はまだ取得されていません。";
    return;
  }

  const sourceRows = stats[config.rowsKey];
  if (!Array.isArray(sourceRows) || sourceRows.length === 0) {
    if (statsLegend) statsLegend.hidden = true;
    statsSummary.append(statCard(config.title, null, "未取得"));
    statsNote.textContent = `${view === "weekly" ? "週次" : "月次"}統計はまだ取得されていません。`;
    return;
  }

  if (statsLegend) statsLegend.hidden = false;
  const rows = sourceRows.slice().sort((a, b) => a[config.sortKey].localeCompare(b[config.sortKey]));
  const latest = rows[rows.length - 1];
  const latestPeriod = rowLabel(view, latest);
  const latestLabel = latest.partial ? `${latestPeriod}（途中）` : latestPeriod;
  statsSummary.append(
    statCard("Public repositories", stats.publicRepositories, `archived ${stats.archivedPublicRepositories}`),
    statCard("Commit", latest.commits, latestLabel),
    statCard("Merged PR", latest.prsMerged, latestLabel),
    statCard("Closed Issue", latest.issuesClosed, latestLabel),
  );

  const maxima = Object.fromEntries(
    STAT_SERIES.map(({ key }) => [
      key,
      Math.max(1, ...rows.map((row) => Number.isInteger(row[key]) ? row[key] : 0)),
    ]),
  );

  for (const row of rows) {
    const line = document.createElement("div");
    line.className = "stats-row";
    line.setAttribute("role", "row");
    if (row.partial) line.dataset.partial = "true";

    const period = document.createElement("strong");
    period.className = "stats-month";
    period.setAttribute("role", "rowheader");
    period.textContent = `${rowLabel(view, row)}${row.partial ? " *" : ""}`;
    line.append(period);

    const series = document.createElement("div");
    series.className = "stats-series";
    for (const spec of STAT_SERIES) {
      const value = Number.isInteger(row[spec.key]) ? row[spec.key] : 0;
      const item = document.createElement("div");
      item.className = "stats-series-item";
      item.dataset.series = spec.key;
      item.setAttribute("role", "cell");

      const label = document.createElement("span");
      label.className = "stats-series-label";
      label.textContent = spec.label;
      const track = document.createElement("span");
      track.className = "stats-track";
      const bar = document.createElement("span");
      bar.className = "stats-bar";
      bar.style.width = `${Math.max(value > 0 ? 3 : 0, (value / maxima[spec.key]) * 100)}%`;
      track.append(bar);
      const number = document.createElement("strong");
      number.className = "stats-value";
      number.textContent = value.toLocaleString("ja-JP");
      item.append(label, track, number);
      series.append(item);
    }
    line.append(series);
    statsMonthly.append(line);
  }

  const weeklyScope = view === "weekly" ? "週次は月曜始まりの直近12週間。" : "";
  statsNote.textContent = `GitHub Search API / ${stats.scope} scope / ${stats.timezone}。${weeklyScope}${config.partialNote}バーは各指標内で相対表示し、数値が実測値です。`;
}
