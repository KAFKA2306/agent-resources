function mountPublicLinks() {
  const sidebar = document.querySelector(".activity-sidebar");
  if (!sidebar || document.querySelector("#public-links")) return;

  const stylesheet = document.createElement("link");
  stylesheet.rel = "stylesheet";
  stylesheet.href = "./public-links.css";
  document.head.append(stylesheet);

  const panel = document.createElement("section");
  panel.className = "public-links-panel";
  panel.setAttribute("aria-label", "公開リンク");

  const heading = document.createElement("div");
  heading.className = "public-links-heading";
  const titleBox = document.createElement("div");
  const eyebrow = document.createElement("p");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = "PUBLIC PRESENCE";
  const title = document.createElement("h2");
  title.textContent = "公開リンク";
  titleBox.append(eyebrow, title);

  const meta = document.createElement("div");
  meta.className = "public-links-meta";
  const state = document.createElement("span");
  state.id = "public-links-status";
  state.className = "status-chip";
  state.dataset.state = "loading";
  state.textContent = "読込中";
  const checked = document.createElement("span");
  checked.id = "public-links-generated-at";
  checked.className = "muted";
  checked.textContent = "確認: 読込中";
  meta.append(state, checked);
  heading.append(titleBox, meta);

  const list = document.createElement("div");
  list.id = "public-links";
  list.className = "public-links-list";
  list.setAttribute("aria-live", "polite");
  panel.append(heading, list);
  sidebar.prepend(panel);
  import("./public-links.js");
}

mountPublicLinks();

const STAT_SERIES = [
  { key: "commits", label: "Commit" },
  { key: "prsMerged", label: "Merged PR" },
  { key: "issuesClosed", label: "Closed Issue" },
];

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

export function renderStats(stats) {
  const statsSummary = document.querySelector("#stats-summary");
  const statsMonthly = document.querySelector("#stats-monthly");
  const statsNote = document.querySelector("#stats-note");
  const statsScope = document.querySelector("#stats-scope");
  if (!statsSummary || !statsMonthly || !statsNote || !statsScope) return;

  statsSummary.replaceChildren();
  statsMonthly.replaceChildren();
  statsScope.textContent = "public only";

  if (!stats || stats.scope !== "public" || !Array.isArray(stats.monthly) || stats.monthly.length === 0) {
    statsSummary.append(statCard("公開統計", null, "未取得"));
    statsNote.textContent = "公開GitHub統計はまだ取得されていません。";
    return;
  }

  const monthly = stats.monthly.slice().sort((a, b) => a.month.localeCompare(b.month));
  const latest = monthly[monthly.length - 1];
  const latestLabel = latest.partial ? `${latest.month}（途中）` : latest.month;
  statsSummary.append(
    statCard("Public repositories", stats.publicRepositories, `archived ${stats.archivedPublicRepositories}`),
    statCard("Commit", latest.commits, latestLabel),
    statCard("Merged PR", latest.prsMerged, latestLabel),
    statCard("Closed Issue", latest.issuesClosed, latestLabel),
  );

  const maxima = Object.fromEntries(
    STAT_SERIES.map(({ key }) => [
      key,
      Math.max(1, ...monthly.map((row) => Number.isInteger(row[key]) ? row[key] : 0)),
    ]),
  );

  for (const row of monthly) {
    const line = document.createElement("div");
    line.className = "stats-row";
    line.setAttribute("role", "row");
    if (row.partial) line.dataset.partial = "true";

    const month = document.createElement("strong");
    month.className = "stats-month";
    month.setAttribute("role", "rowheader");
    month.textContent = `${row.month}${row.partial ? " *" : ""}`;
    line.append(month);

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

  statsNote.textContent = `GitHub Search API / ${stats.scope} scope / ${stats.timezone}。* は当月途中集計。バーは各指標内で相対表示し、数値が実測値です。`;
}
