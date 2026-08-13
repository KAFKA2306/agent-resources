const root = document.querySelector("#public-links");
const status = document.querySelector("#public-links-status");
const checkedAt = document.querySelector("#public-links-generated-at");

const CATEGORY_LABELS = {
  app: "APP",
  creator: "CREATOR",
  media: "MEDIA",
  profile: "PROFILE",
  social: "SOCIAL",
  writing: "WRITING",
};

function formatTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "不明";
  return new Intl.DateTimeFormat("ja-JP", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function render(payload) {
  const links = Array.isArray(payload.links) ? payload.links : [];
  root.replaceChildren();
  for (const item of links) {
    const link = document.createElement("a");
    link.className = "public-link-item";
    link.href = item.url;
    link.target = "_blank";
    link.rel = "noreferrer";

    const meta = document.createElement("span");
    meta.className = "public-link-meta";
    meta.textContent = `${CATEGORY_LABELS[item.category] || item.category.toUpperCase()} · ${item.provider}`;

    const label = document.createElement("strong");
    label.textContent = item.label;
    link.append(meta, label);
    root.append(link);
  }

  const vercel = payload.sourceStatus?.vercel;
  if (vercel?.status === "ok" || vercel?.status === "partial") {
    status.textContent = `Vercel ${vercel.ready}/${vercel.discovered} READY`;
    status.dataset.state = vercel.status === "ok" ? "fresh" : "stale";
  } else if (vercel?.status === "unavailable") {
    status.textContent = "Vercel token未接続";
    status.dataset.state = "unknown";
  } else if (vercel?.status === "error") {
    status.textContent = "Vercel取得失敗";
    status.dataset.state = "failed";
  } else {
    status.textContent = `${links.length} links`;
    status.dataset.state = "fresh";
  }
  checkedAt.textContent = `確認: ${formatTime(payload.generatedAt)}`;
}

async function load() {
  try {
    const response = await fetch("./public-links.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
  } catch (error) {
    root.replaceChildren();
    status.textContent = "公開リンク取得失敗";
    status.dataset.state = "failed";
    checkedAt.textContent = "確認: 取得できません";
    console.error(error);
  }
}

load();
