export const OWNER = "KAFKA2306";
export const LIVE_SCHEMA_VERSION = "1.0.0";
export const LIVE_CACHE_SECONDS = 600;
export const LIVE_STALE_WHILE_REVALIDATE_SECONDS = 30;
export const ACTIVITY_WINDOW_DAYS = 7;
export const MAX_ACTIVITY_ITEMS = 200;

export class LiveDataError extends Error {
  constructor(code, message, details = {}) {
    super(message);
    this.name = "LiveDataError";
    this.code = code;
    this.details = details;
  }
}

function requireString(value, field) {
  if (typeof value !== "string" || !value) throw new LiveDataError("invalid_upstream_payload", `missing ${field}`);
  return value;
}

export function normalizeRepository(raw, owner = OWNER) {
  if (raw?.owner?.login !== owner) return null;
  if (raw?.private === true || raw?.visibility !== "public" || raw?.archived === true) return null;
  if (typeof raw?.archived !== "boolean") throw new LiveDataError("invalid_upstream_payload", "repository archived flag is missing");
  return {
    id: requireString(raw.node_id, "repository node_id"),
    owner,
    name: requireString(raw.name, "repository name"),
    url: requireString(raw.html_url, "repository html_url"),
    visibility: "public",
    archived: false,
    updatedAt: requireString(raw.updated_at, "repository updated_at"),
    pushedAt: raw.pushed_at || null,
  };
}

export function classifyLane(item) {
  if (item.kind === "issue" && item.state === "open") return { lane: "working", laneReason: "open_issue" };
  if (item.kind === "pull_request" && item.state === "open") return { lane: "waiting", laneReason: "open_pull_request" };
  if (item.kind === "workflow_run") {
    if (["queued", "in_progress"].includes(item.state)) return { lane: "working", laneReason: `workflow_${item.state}` };
    if (["completed", "skipped"].includes(item.state)) return { lane: "done", laneReason: `workflow_${item.state}` };
    if (["failed", "cancelled"].includes(item.state)) return { lane: "failed", laneReason: `workflow_${item.state}` };
  }
  return { lane: "waiting", laneReason: "unknown_state_requires_review" };
}

function addLane(item) {
  return { ...item, ...classifyLane(item) };
}

export function workflowState(run) {
  const status = run?.status;
  const conclusion = run?.conclusion;
  if (["queued", "requested", "waiting", "pending"].includes(status)) return "queued";
  if (status === "in_progress") return "in_progress";
  if (status !== "completed") throw new LiveDataError("invalid_upstream_payload", `unknown workflow status: ${String(status)}`);
  if (conclusion === "success") return "completed";
  if (["neutral", "skipped"].includes(conclusion)) return "skipped";
  if (conclusion === "cancelled") return "cancelled";
  if (["failure", "timed_out", "action_required", "stale", "startup_failure"].includes(conclusion)) return "failed";
  throw new LiveDataError("invalid_upstream_payload", `unknown workflow conclusion: ${String(conclusion)}`);
}

export function normalizeWorkflowRun(raw, repository) {
  if (!raw) return null;
  if (!Number.isInteger(raw.id) || raw.id < 1 || !Number.isInteger(raw.run_number) || raw.run_number < 1) {
    throw new LiveDataError("invalid_upstream_payload", "workflow run id/number is invalid");
  }
  const item = {
    id: `${repository.id}:workflow_run:${raw.id}`,
    repositoryId: repository.id,
    kind: "workflow_run",
    number: raw.run_number,
    title: requireString(raw.name, "workflow name"),
    url: requireString(raw.html_url, "workflow html_url"),
    state: workflowState(raw),
    updatedAt: requireString(raw.updated_at, "workflow updated_at"),
  };
  return addLane(item);
}

function repositoryFullNameFromSearchItem(raw) {
  const value = raw?.repository_url;
  if (typeof value !== "string") return null;
  try {
    const parts = new URL(value).pathname.split("/").filter(Boolean);
    const reposIndex = parts.indexOf("repos");
    if (reposIndex < 0 || parts.length <= reposIndex + 2) return null;
    return `${parts[reposIndex + 1]}/${parts[reposIndex + 2]}`;
  } catch {
    return null;
  }
}

export function normalizeSearchWorkItem(raw, repositoriesByFullName) {
  if (raw?.state !== "open") return null;
  const fullName = repositoryFullNameFromSearchItem(raw);
  const repository = fullName ? repositoriesByFullName.get(fullName.toLowerCase()) : null;
  if (!repository) return null;
  const kind = raw.pull_request ? "pull_request" : "issue";
  if (!Number.isInteger(raw.number) || raw.number < 1) throw new LiveDataError("invalid_upstream_payload", "work item number is invalid");
  return addLane({
    id: `${repository.id}:${kind}:${raw.number}`,
    kind,
    repositoryId: repository.id,
    number: raw.number,
    title: requireString(raw.title, "work item title"),
    url: requireString(raw.html_url, "work item html_url"),
    state: "open",
    updatedAt: requireString(raw.updated_at, "work item updated_at"),
  });
}

export function normalizeSearchActivity(raw, repositoriesByFullName) {
  const fullName = repositoryFullNameFromSearchItem(raw);
  const repository = fullName ? repositoriesByFullName.get(fullName.toLowerCase()) : null;
  if (!repository) return null;
  const kind = raw.pull_request ? "pull_request" : "issue";
  if (!Number.isInteger(raw.number) || raw.number < 1) throw new LiveDataError("invalid_upstream_payload", "activity number is invalid");
  return {
    id: `activity:${repository.id}:${kind}:${raw.number}`,
    repositoryId: repository.id,
    kind,
    occurredAt: requireString(raw.updated_at, "activity updated_at"),
    url: requireString(raw.html_url, "activity html_url"),
    summary: requireString(raw.title, "activity title"),
  };
}

function toWorkflowActivity(item) {
  return {
    id: `activity:${item.id}`,
    repositoryId: item.repositoryId,
    kind: "workflow_run",
    occurredAt: item.updatedAt,
    url: item.url,
    summary: item.title,
  };
}

function isoDateDaysAgo(now, days) {
  return new Date(now.getTime() - days * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
}

function parseTime(value) {
  const time = Date.parse(value);
  return Number.isFinite(time) ? time : null;
}

export function buildActivity(searchItems, workflowItems, now = new Date()) {
  const cutoff = now.getTime() - ACTIVITY_WINDOW_DAYS * 24 * 60 * 60 * 1000;
  const upper = now.getTime() + 5 * 60 * 1000;
  const byId = new Map();
  for (const item of [...searchItems, ...workflowItems.map(toWorkflowActivity)]) {
    const timestamp = parseTime(item.occurredAt);
    if (timestamp === null || timestamp < cutoff || timestamp > upper) continue;
    const current = byId.get(item.id);
    if (!current || item.occurredAt > current.occurredAt) byId.set(item.id, item);
  }
  return [...byId.values()]
    .sort((a, b) => b.occurredAt.localeCompare(a.occurredAt) || b.id.localeCompare(a.id))
    .slice(0, MAX_ACTIVITY_ITEMS);
}

function captureRateLimit(headers, rateLimits) {
  if (!headers?.get) return;
  const resource = headers.get("x-ratelimit-resource") || "core";
  const limit = Number(headers.get("x-ratelimit-limit"));
  const remaining = Number(headers.get("x-ratelimit-remaining"));
  const reset = Number(headers.get("x-ratelimit-reset"));
  if (!Number.isFinite(limit) || !Number.isFinite(remaining)) return;
  const next = {
    limit,
    remaining,
    resetAt: Number.isFinite(reset) ? new Date(reset * 1000).toISOString() : null,
  };
  const current = rateLimits[resource];
  if (!current || next.remaining < current.remaining) rateLimits[resource] = next;
}

async function requestJson(url, context) {
  context.requestCount += 1;
  const response = await context.fetchImpl(url, {
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${context.token}`,
      "User-Agent": "agent-resources-live-dashboard",
      "X-GitHub-Api-Version": "2022-11-28",
    },
  });
  captureRateLimit(response.headers, context.rateLimits);
  if (!response.ok) {
    const retryAfter = response.headers?.get?.("retry-after") || null;
    const remaining = response.headers?.get?.("x-ratelimit-remaining") || null;
    const code = response.status === 403 || response.status === 429 ? "github_rate_limited" : "github_upstream_error";
    throw new LiveDataError(code, `GitHub API returned HTTP ${response.status}`, { status: response.status, retryAfter, remaining });
  }
  try {
    return await response.json();
  } catch {
    throw new LiveDataError("invalid_upstream_payload", "GitHub API returned invalid JSON");
  }
}

async function listRepositories(context) {
  const output = [];
  for (let page = 1; page <= 5; page += 1) {
    const url = `https://api.github.com/users/${encodeURIComponent(context.owner)}/repos?per_page=100&type=owner&sort=updated&page=${page}`;
    const payload = await requestJson(url, context);
    if (!Array.isArray(payload)) throw new LiveDataError("invalid_upstream_payload", "repository response must be an array");
    for (const raw of payload) {
      const normalized = normalizeRepository(raw, context.owner);
      if (normalized) output.push(normalized);
    }
    if (payload.length < 100) break;
    if (page === 5) throw new LiveDataError("request_budget_exceeded", "repository pagination exceeded five pages");
  }
  output.sort((a, b) => a.name.localeCompare(b.name));
  return output;
}

async function searchIssues(context, query, maxPages) {
  const output = [];
  for (let page = 1; page <= maxPages; page += 1) {
    const params = new URLSearchParams({ q: query, sort: "updated", order: "desc", per_page: "100", page: String(page) });
    const payload = await requestJson(`https://api.github.com/search/issues?${params}`, context);
    if (!payload || !Array.isArray(payload.items)) throw new LiveDataError("invalid_upstream_payload", "issue search response must contain items");
    output.push(...payload.items);
    if (payload.items.length < 100 || output.length >= Number(payload.total_count || 0)) break;
  }
  return output;
}

async function searchIssuesAndPullRequests(context, baseQuery, maxPages) {
  const [issues, pullRequests] = await Promise.all([
    searchIssues(context, `${baseQuery} is:issue`, maxPages),
    searchIssues(context, `${baseQuery} is:pull-request`, maxPages),
  ]);
  return [...issues, ...pullRequests];
}

export async function collectLiveState({ token, fetchImpl = globalThis.fetch, owner = OWNER, now = new Date() } = {}) {
  if (!token) throw new LiveDataError("missing_server_credential", "DASHBOARD_GITHUB_TOKEN is required");
  if (typeof fetchImpl !== "function") throw new TypeError("fetchImpl must be a function");
  const context = { token, fetchImpl, owner, requestCount: 0, workflowRequestCount: 0, rateLimits: {} };
  const repositories = await listRepositories(context);
  const repositoriesByFullName = new Map(repositories.map((repo) => [`${repo.owner}/${repo.name}`.toLowerCase(), repo]));

  const openRaw = await searchIssuesAndPullRequests(context, `user:${owner} is:open`, 10);
  const workItems = openRaw
    .map((raw) => normalizeSearchWorkItem(raw, repositoriesByFullName))
    .filter(Boolean);

  const activityRaw = await searchIssuesAndPullRequests(
    context,
    `user:${owner} updated:>=${isoDateDaysAgo(now, ACTIVITY_WINDOW_DAYS)}`,
    2,
  );
  const activity = activityRaw
    .map((raw) => normalizeSearchActivity(raw, repositoriesByFullName))
    .filter(Boolean);

  const allWorkItems = [...workItems].sort((a, b) =>
    a.repositoryId.localeCompare(b.repositoryId) || a.kind.localeCompare(b.kind) || a.number - b.number,
  );

  const fetchedAt = now.toISOString();
  return {
    schemaVersion: LIVE_SCHEMA_VERSION,
    source: "github-rest",
    scope: "public",
    owner,
    fetchedAt,
    cache: {
      maxAgeSeconds: LIVE_CACHE_SECONDS,
      staleWhileRevalidateSeconds: LIVE_STALE_WHILE_REVALIDATE_SECONDS,
    },
    requestBudget: {
      requestCount: context.requestCount,
      workflowRequestCount: context.workflowRequestCount,
      repositoryCount: repositories.length,
      theoreticalRequestsPerHourAtMaxAge: Math.ceil(3600 / LIVE_CACHE_SECONDS) * context.requestCount,
    },
    rateLimits: context.rateLimits,
    summary: {
      repositoryCount: repositories.length,
      workItemCount: allWorkItems.length,
      activityCount: activity.length,
    },
    repositories,
    workItems: allWorkItems,
    activity,
  };
}
