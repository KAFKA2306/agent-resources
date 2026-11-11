const HISTORY_URL = "./issue-backlog-history.json";
const SVG_NS = "http://www.w3.org/2000/svg";

function svgElement(tag, attributes = {}, text = null) {
  const element = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  if (text !== null) element.textContent = text;
  return element;
}

function validSnapshots(payload) {
  if (payload?.schemaVersion !== 1 || payload?.scope !== "public" || payload?.timezone !== "Asia/Tokyo" || !Array.isArray(payload.snapshots)) {
    throw new Error("公開Issue履歴の形式が一致しません");
  }
  const rows = payload.snapshots.filter((row) =>
    /^\d{4}-\d{2}-\d{2}$/.test(row?.date || "") &&
    !Number.isNaN(Date.parse(row.date)) &&
    Number.isSafeInteger(row.allOpen) && row.allOpen >= 0 &&
    Number.isSafeInteger(row.authoredOpen) && row.authoredOpen >= 0 &&
    !Number.isNaN(Date.parse(row.observedAt))
  ).sort((a, b) => a.date.localeCompare(b.date));
  if (rows.length !== payload.snapshots.length || new Set(rows.map((row) => row.date)).size !== rows.length) {
    throw new Error("Issue履歴に不正な計測値または重複日付があります");
  }
  return rows;
}

function card(label, value, detail) {
  const element = document.createElement("div");
  element.className = "stat-card";
  const name = document.createElement("span");
  name.textContent = label;
  const number = document.createElement("strong");
  number.textContent = value;
  const caption = document.createElement("small");
  caption.textContent = detail;
  element.append(name, number, caption);
  return element;
}

function issueHistoryTable(rows) {
  const details = document.createElement("details");
  details.className = "issue-history-details";
  const summary = document.createElement("summary");
  summary.textContent = "日別の件数を表で確認";
  const scroll = document.createElement("div");
  scroll.className = "issue-history-scroll";
  const table = document.createElement("table");
  const caption = document.createElement("caption");
  caption.textContent = "公開Issueの日次観測値（JST）";
  const head = document.createElement("thead");
  const tr = document.createElement("tr");
  for (const label of ["観測日", "所有リポ内", "本人が作成", "所有リポ内の前回差"]) {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = label;
    tr.append(th);
  }
  head.append(tr);
  const body = document.createElement("tbody");
  rows.forEach((row, index) => {
    const tr = document.createElement("tr");
    const th = document.createElement("th");
    th.scope = "row";
    th.textContent = row.date;
    tr.append(th);
    const delta = index ? row.allOpen - rows[index - 1].allOpen : null;
    for (const value of [row.allOpen.toLocaleString("ja-JP"), row.authoredOpen.toLocaleString("ja-JP"), delta === null ? "—" : (delta > 0 ? "+" : "") + delta.toLocaleString("ja-JP")]) {
      const td = document.createElement("td");
      td.textContent = value;
      tr.append(td);
    }
    body.append(tr);
  });
  table.append(caption, head, body);
  scroll.append(table);
  details.append(summary, scroll);
  return details;
}

function renderIssueHistory(payload) {
  const summary = document.querySelector("#issue-history-summary");
  const chart = document.querySelector("#issue-history-chart");
  const note = document.querySelector("#issue-history-note");
  if (!summary || !chart || !note) return;
  const rows = validSnapshots(payload);
  summary.replaceChildren();
  chart.replaceChildren();
  if (!rows.length) {
    chart.textContent = "まだ観測値がありません。初回の収集後に推移を表示します。";
    return;
  }
  const first = rows[0];
  const latest = rows[rows.length - 1];
  const delta = latest.allOpen - first.allOpen;
  summary.append(
    card("所有リポジトリ内", latest.allOpen.toLocaleString("ja-JP") + "件", latest.date + " 時点"),
    card("本人が作成", latest.authoredOpen.toLocaleString("ja-JP") + "件", "所有リポジトリ外も含む"),
    card("初回観測からの増減", rows.length > 1 ? (delta > 0 ? "+" : "") + delta.toLocaleString("ja-JP") + "件" : "—", rows.length + "日分の観測")
  );

  const svg = svgElement("svg", {
    viewBox: "0 0 940 335",
    role: "img",
    "aria-label": "未解決Issueの推移。所有リポジトリ内は" + first.allOpen + "件から" + latest.allOpen + "件、本人が作成したIssueは" + first.authoredOpen + "件から" + latest.authoredOpen + "件。目盛りは件数です"
  });
  const values = rows.flatMap((row) => [row.allOpen, row.authoredOpen]);
  const low = Math.min(...values);
  const high = Math.max(...values);
  const span = Math.max(1, high - low);
  const pad = Math.max(2, Math.ceil(span * 0.12));
  const desiredStep = (span + pad * 2) / 4;
  const magnitude = 10 ** Math.floor(Math.log10(desiredStep));
  const step = [1, 2, 5, 10].map((n) => n * magnitude).find((n) => n >= desiredStep) || magnitude * 10;
  const min = Math.max(0, Math.floor((low - pad) / step) * step);
  const max = Math.max(min + step, Math.ceil((high + pad) / step) * step);
  const x = (i) => rows.length === 1 ? 490 : 98 + i * 792 / (rows.length - 1);
  const y = (value) => 274 - (value - min) * 235 / (max - min);
  for (let value = min; value <= max + step * 0.001; value += step) {
    const py = y(value);
    svg.append(svgElement("line", { x1: 98, x2: 890, y1: py, y2: py, class: "issue-history-grid" }));
    svg.append(svgElement("text", { x: 85, y: py + 4, "text-anchor": "end", class: "issue-history-axis" }, value.toLocaleString("ja-JP")));
  }
  const indices = rows.length <= 3
    ? rows.map((_, i) => i)
    : [...new Set([0, Math.floor((rows.length - 1) / 4), Math.floor((rows.length - 1) / 2), Math.floor((rows.length - 1) * 3 / 4), rows.length - 1])];
  for (const index of indices) {
    svg.append(svgElement("text", { x: x(index), y: 310, "text-anchor": "middle", class: "issue-history-axis" }, rows[index].date.slice(5)));
  }
  if (min > 0) svg.append(svgElement("text", { x: 98, y: 20, class: "issue-history-axis" }, "件数・縦軸は0始まりではありません"));
  for (const series of [{ key: "allOpen", css: "all", label: "所有リポ内" }, { key: "authoredOpen", css: "authored", label: "本人が作成" }]) {
    const points = rows.map((row, index) => x(index).toFixed(1) + "," + y(row[series.key]).toFixed(1)).join(" ");
    if (rows.length > 1) svg.append(svgElement("polyline", { points, class: "issue-history-line is-" + series.css }));
    rows.forEach((row, index) => {
      const point = svgElement("circle", {
        cx: x(index), cy: y(row[series.key]), r: 4.3, class: "issue-history-point is-" + series.css,
        tabindex: "0", role: "img",
        "aria-label": row.date + " " + series.label + " " + row[series.key] + "件"
      });
      point.append(svgElement("title", {}, row.date + " " + series.label + " " + row[series.key].toLocaleString("ja-JP") + "件"));
      svg.append(point);
    });
  }
  chart.append(svg, issueHistoryTable(rows));
  note.textContent = "日次スナップショット: " + first.date + "〜" + latest.date +
    "。所有リポ内＝KAFKA2306所有の公開リポジトリにある未解決Issue、本人が作成＝リポジトリの所有者を問わず本人作成の公開未解決Issue。対象範囲が異なるため、2系列の差は内訳ではありません。";
}

async function loadIssueHistory() {
  const chart = document.querySelector("#issue-history-chart");
  if (!chart) return;
  try {
    const response = await fetch(HISTORY_URL, { cache: "no-store" });
    if (!response.ok) throw new Error("HTTP " + response.status);
    renderIssueHistory(await response.json());
  } catch (error) {
    chart.replaceChildren();
    chart.textContent = "履歴を取得できません（" + (error instanceof Error ? error.message : "不明なエラー") + "）。未確認の件数は表示しません。";
  }
}
loadIssueHistory();
