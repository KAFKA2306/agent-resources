const STATUS_LABELS = {
  disabled: "disabled",
  running: "running",
  ok: "ok",
  error: "error",
  skipped: "skipped",
  idle: "idle",
  unknown: "unknown",
};

function formatTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "取得時刻不明";
  return new Intl.DateTimeFormat("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function renderOpenClawRuntime(runtime) {
  const section = document.querySelector("#openclaw-runtime");
  const cards = document.querySelector("#openclaw-runtime-agents");
  const meta = document.querySelector("#openclaw-runtime-meta");
  if (!section || !cards || !meta) return;

  if (!runtime || runtime.scope !== "domain-agents" || !Array.isArray(runtime.agents)) {
    section.hidden = true;
    return;
  }

  const automations = Array.isArray(runtime.automations) ? runtime.automations : [];
  cards.replaceChildren();
  for (const agent of runtime.agents) {
    const card = document.createElement("article");
    card.className = "openclaw-agent-card";

    const heading = document.createElement("div");
    heading.className = "openclaw-agent-heading";
    const name = document.createElement("strong");
    name.textContent = agent.id;
    const sessionCount = document.createElement("span");
    sessionCount.textContent = `${agent.sessionCount || 0} sessions`;
    heading.append(name, sessionCount);

    const jobs = automations.filter((job) => job.agentId === agent.id);
    const jobList = document.createElement("div");
    jobList.className = "openclaw-job-list";
    if (jobs.length === 0) {
      const empty = document.createElement("span");
      empty.className = "muted";
      empty.textContent = "automation なし";
      jobList.append(empty);
    } else {
      for (const job of jobs) {
        const row = document.createElement("div");
        row.className = "openclaw-job";
        row.dataset.status = job.status;
        const label = document.createElement("span");
        label.textContent = job.name;
        const status = document.createElement("strong");
        status.textContent = STATUS_LABELS[job.status] || "unknown";
        row.append(label, status);
        jobList.append(row);
      }
    }

    const models = document.createElement("p");
    models.className = "openclaw-models muted";
    models.textContent = Array.isArray(agent.models) && agent.models.length ? agent.models.join(" · ") : "model observation なし";
    card.append(heading, jobList, models);
    cards.append(card);
  }

  meta.textContent = `Local snapshot: ${formatTime(runtime.collectedAt)}`;
  section.hidden = false;
}

async function loadOpenClawRuntime() {
  try {
    const response = await fetch("./dashboard.json", { cache: "no-store" });
    if (!response.ok) return;
    const snapshot = await response.json();
    renderOpenClawRuntime(snapshot.openclawRuntime);
  } catch (error) {
    console.warn("OpenClaw runtime snapshot unavailable", error);
  }
}

if (typeof document !== "undefined" && typeof fetch === "function") {
  loadOpenClawRuntime();
}
