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
  statsScope.textContent = "PUBLIC";
  statsMonthly.dataset.view = view;
  statsMonthly.setAttribute("aria-label", config.ariaLabel);
  statsMonthly.setAttribute("role", "img");
  if (statsTitle) statsTitle.textContent = view === "weekly" ? "OUTPUT / 12W" : "OUTPUT / YTD";
  if (statsLegend) statsLegend.hidden = true;
  statsNote.textContent = "";

  if (!stats || stats.scope !== "public") {
    statsSummary.append(statCard("PUBLIC", null, "NO DATA"));
    return;
  }

  const sourceRows = stats[config.rowsKey];
  if (!Array.isArray(sourceRows) || sourceRows.length === 0) {
    statsSummary.append(statCard(view === "weekly" ? "12W" : "YTD", null, "NO DATA"));
    return;
  }

  const rows = sourceRows.slice().sort((a, b) => a[config.sortKey].localeCompare(b[config.sortKey]));
  const latest = rows[rows.length - 1];
  statsSummary.append(
    statCard("REPOS", stats.publicRepositories, ""),
    statCard("COMMIT", latest.commits, ""),
    statCard("MERGE", latest.prsMerged, ""),
    statCard("CLOSE", latest.issuesClosed, ""),
  );

  const SVG_NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.classList.add("output-waveform");
  svg.setAttribute("viewBox", "0 0 1000 330");
  svg.setAttribute("aria-label", config.ariaLabel);

  const bands = [
    { ...STAT_SERIES[0], y: 70, className: "commits" },
    { ...STAT_SERIES[1], y: 165, className: "prsMerged" },
    { ...STAT_SERIES[2], y: 260, className: "issuesClosed" },
  ];
  const x = (index) => rows.length <= 1 ? 500 : 110 + (index / (rows.length - 1)) * 780;

  for (const band of bands) {
    const values = rows.map((row) => Number.isInteger(row[band.key]) ? row[band.key] : 0);
    const max = Math.max(1, ...values);
    const guide = document.createElementNS(SVG_NS, "line");
    guide.setAttribute("x1", "100");
    guide.setAttribute("x2", "900");
    guide.setAttribute("y1", String(band.y));
    guide.setAttribute("y2", String(band.y));
    guide.classList.add("wave-guide");
    svg.append(guide);

    const label = document.createElementNS(SVG_NS, "text");
    label.setAttribute("x", "20");
    label.setAttribute("y", String(band.y + 4));
    label.classList.add("wave-label", `is-${band.className}`);
    label.textContent = band.label.toUpperCase();
    svg.append(label);

    const current = document.createElementNS(SVG_NS, "text");
    current.setAttribute("x", "970");
    current.setAttribute("y", String(band.y + 5));
    current.setAttribute("text-anchor", "end");
    current.classList.add("wave-value", `is-${band.className}`);
    current.textContent = String(values[values.length - 1] || 0);
    svg.append(current);

    const polyline = document.createElementNS(SVG_NS, "polyline");
    polyline.classList.add("wave-line", `is-${band.className}`);
    polyline.setAttribute(
      "points",
      values.map((value, index) => {
        const amplitude = (value / max) * 34;
        return `${x(index).toFixed(1)},${(band.y + 24 - amplitude).toFixed(1)}`;
      }).join(" "),
    );
    svg.append(polyline);

    values.forEach((value, index) => {
      const amplitude = (value / max) * 34;
      const cy = band.y + 24 - amplitude;
      const point = document.createElementNS(SVG_NS, "circle");
      point.setAttribute("cx", x(index).toFixed(1));
      point.setAttribute("cy", cy.toFixed(1));
      point.setAttribute("r", "3.2");
      point.classList.add("wave-point", `is-${band.className}`);
      const title = document.createElementNS(SVG_NS, "title");
      title.textContent = `${rowLabel(view, rows[index])} · ${band.label} ${value}`;
      point.append(title);
      svg.append(point);
    });
  }

  const firstLabel = document.createElementNS(SVG_NS, "text");
  firstLabel.setAttribute("x", "110");
  firstLabel.setAttribute("y", "320");
  firstLabel.classList.add("wave-period");
  firstLabel.textContent = rowLabel(view, rows[0]);
  const lastLabel = document.createElementNS(SVG_NS, "text");
  lastLabel.setAttribute("x", "890");
  lastLabel.setAttribute("y", "320");
  lastLabel.setAttribute("text-anchor", "end");
  lastLabel.classList.add("wave-period");
  lastLabel.textContent = rowLabel(view, rows[rows.length - 1]);
  svg.append(firstLabel, lastLabel);

  statsMonthly.append(svg);
}

