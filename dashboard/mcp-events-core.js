import { createHash, createHmac, timingSafeEqual } from "node:crypto";

export const MCP_PROTOCOL_VERSION = "2026-07-28";
export const DEFAULT_SUBSCRIPTION_TTL_MS = 7 * 24 * 60 * 60 * 1000;
export const MIN_SUBSCRIPTION_TTL_MS = 60 * 60 * 1000;
export const MAX_SUBSCRIPTION_TTL_MS = 7 * 24 * 60 * 60 * 1000;
export const VERIFICATION_CACHE_MS = 15 * 60 * 1000;
export const MAX_EVENT_BYTES = 256 * 1024;

const issueFilter = {
  type: "object",
  properties: {
    repository: {
      type: "string",
      description: "GitHub repository in owner/name form. This pilot supports KAFKA2306/agent-resources.",
    },
    number: {
      type: "integer",
      minimum: 1,
      description: "Optional issue or pull request number to monitor.",
    },
  },
  required: ["repository"],
  additionalProperties: false,
};

const workflowFilter = {
  type: "object",
  properties: {
    repository: {
      type: "string",
      description: "GitHub repository in owner/name form. This pilot supports KAFKA2306/agent-resources.",
    },
    workflow: {
      type: "string",
      minLength: 1,
      description: "Optional exact workflow name to monitor.",
    },
  },
  required: ["repository"],
  additionalProperties: false,
};

const commonPayloadProperties = {
  repository: { type: "string" },
  action: { type: "string" },
  actor: { type: "string" },
  url: { type: "string" },
  title: { type: ["string", "null"] },
  number: { type: ["integer", "null"] },
  text: { type: ["string", "null"] },
  head_sha: { type: ["string", "null"] },
  workflow: { type: ["string", "null"] },
  conclusion: { type: ["string", "null"] },
};

function eventDefinition(name, description, inputSchema = issueFilter) {
  return {
    name,
    description,
    delivery: ["webhook"],
    inputSchema,
    payloadSchema: {
      type: "object",
      properties: commonPayloadProperties,
      required: ["repository", "action", "actor", "url"],
      additionalProperties: false,
    },
  };
}

export const EVENT_DEFINITIONS = Object.freeze([
  eventDefinition("github.issue.opened", "A GitHub issue was opened in the selected repository."),
  eventDefinition("github.issue.closed", "A GitHub issue was closed in the selected repository."),
  eventDefinition("github.issue.reopened", "A GitHub issue was reopened in the selected repository."),
  eventDefinition("github.issue_comment.created", "A new comment was added to an issue or pull request."),
  eventDefinition("github.pull_request.opened", "A GitHub pull request was opened."),
  eventDefinition("github.pull_request.updated", "A GitHub pull request received new commits."),
  eventDefinition("github.pull_request.closed", "A GitHub pull request was closed or merged."),
  eventDefinition("github.pull_request.reopened", "A GitHub pull request was reopened."),
  eventDefinition("github.pull_request_review.submitted", "A review was submitted on a GitHub pull request."),
  eventDefinition(
    "github.workflow_run.completed",
    "A selected GitHub Actions workflow run completed.",
    workflowFilter,
  ),
]);

const EVENT_NAMES = new Set(EVENT_DEFINITIONS.map((event) => event.name));

export function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

export function deterministicSubscriptionId({ principal, callbackUrl, name, arguments: args }) {
  const digest = createHash("sha256")
    .update(`${principal}\n${callbackUrl}\n${name}\n${canonicalJson(args || {})}`)
    .digest("base64url")
    .slice(0, 32);
  return `sub_${digest}`;
}

export function verificationCacheKey({ principal, callbackUrl }) {
  return createHash("sha256")
    .update(`${principal}\n${callbackUrl}`)
    .digest("base64url")
    .slice(0, 40);
}

export function validateWhsec(secret) {
  if (typeof secret !== "string" || !secret.startsWith("whsec_")) return false;
  const encoded = secret.slice("whsec_".length);
  if (!/^[A-Za-z0-9+/]+={0,2}$/.test(encoded)) return false;
  try {
    const decoded = Buffer.from(encoded, "base64");
    return decoded.length >= 24 && decoded.length <= 64;
  } catch {
    return false;
  }
}

export function signStandardWebhook(secret, webhookId, timestampSeconds, body) {
  if (!validateWhsec(secret)) throw new Error("invalid signing secret");
  if (typeof webhookId !== "string" || webhookId.includes(".")) {
    throw new Error("invalid webhook id");
  }
  const key = Buffer.from(secret.slice("whsec_".length), "base64");
  const signature = createHmac("sha256", key)
    .update(`${webhookId}.${timestampSeconds}.${body}`)
    .digest("base64");
  return `v1,${signature}`;
}

export function constantTimeTextEqual(left, right) {
  const a = Buffer.from(String(left ?? ""));
  const b = Buffer.from(String(right ?? ""));
  return a.length === b.length && timingSafeEqual(a, b);
}

export function grantedExpiration(nowMs, requestedTtlMs) {
  let ttl = requestedTtlMs;
  if (ttl === undefined || ttl === null) ttl = DEFAULT_SUBSCRIPTION_TTL_MS;
  if (!Number.isFinite(ttl)) ttl = DEFAULT_SUBSCRIPTION_TTL_MS;
  ttl = Math.max(MIN_SUBSCRIPTION_TTL_MS, Math.min(MAX_SUBSCRIPTION_TTL_MS, Math.trunc(ttl)));
  return new Date(nowMs + ttl).toISOString();
}

export function validateSubscriptionArguments(name, args) {
  if (!EVENT_NAMES.has(name)) return { ok: false, reason: "unknown_event" };
  if (!args || typeof args !== "object" || Array.isArray(args)) {
    return { ok: false, reason: "invalid_arguments" };
  }
  const allowedKeys = name === "github.workflow_run.completed"
    ? new Set(["repository", "workflow"])
    : new Set(["repository", "number"]);
  for (const key of Object.keys(args)) {
    if (!allowedKeys.has(key)) return { ok: false, reason: "invalid_arguments" };
  }
  if (args.repository !== "KAFKA2306/agent-resources") {
    return { ok: false, reason: "repository_not_allowed" };
  }
  if ("number" in args && (!Number.isInteger(args.number) || args.number < 1)) {
    return { ok: false, reason: "invalid_arguments" };
  }
  if ("workflow" in args && (typeof args.workflow !== "string" || !args.workflow.trim())) {
    return { ok: false, reason: "invalid_arguments" };
  }
  return { ok: true };
}

export function validateDelivery(delivery) {
  if (!delivery || typeof delivery !== "object") return { ok: false, reason: "invalid_delivery" };
  if (delivery.mode !== "webhook") return { ok: false, reason: "unsupported_delivery_mode" };
  if (typeof delivery.url !== "string") return { ok: false, reason: "invalid_callback_url" };
  let parsed;
  try {
    parsed = new URL(delivery.url);
  } catch {
    return { ok: false, reason: "invalid_callback_url" };
  }
  if (parsed.protocol !== "https:" || parsed.username || parsed.password || (parsed.port && parsed.port !== "443")) {
    return { ok: false, reason: "invalid_callback_url" };
  }
  if (!validateWhsec(delivery.secret)) return { ok: false, reason: "invalid_signing_secret" };
  return { ok: true, url: parsed.toString() };
}

function safeText(value, limit = 4000) {
  if (typeof value !== "string") return null;
  return value.length <= limit ? value : `${value.slice(0, limit)}…`;
}

function actor(payload) {
  return payload?.sender?.login || payload?.actor?.login || "unknown";
}

function baseData(payload, subject = {}) {
  return {
    repository: payload?.repository?.full_name || "",
    action: String(payload?.action || ""),
    actor: actor(payload),
    url: subject.html_url || payload?.repository?.html_url || "",
    title: safeText(subject.title, 500),
    number: Number.isInteger(subject.number) ? subject.number : null,
    text: null,
    head_sha: null,
    workflow: null,
    conclusion: null,
  };
}

export function githubEventToMcp(githubEventName, payload) {
  const action = String(payload?.action || "");
  const repository = payload?.repository?.full_name;
  if (repository !== "KAFKA2306/agent-resources") return null;

  if (githubEventName === "issues" && ["opened", "closed", "reopened"].includes(action)) {
    const issue = payload.issue || {};
    const data = baseData(payload, issue);
    data.text = safeText(issue.body);
    return makeEvent(`github.issue.${action}`, `issue:${issue.id}:${action}:${issue.updated_at || ""}`, data, issue.updated_at || issue.created_at);
  }

  if (githubEventName === "issue_comment" && action === "created") {
    const issue = payload.issue || {};
    const comment = payload.comment || {};
    const data = baseData(payload, issue);
    data.url = comment.html_url || data.url;
    data.text = safeText(comment.body);
    return makeEvent("github.issue_comment.created", `comment:${comment.id}`, data, comment.created_at);
  }

  if (githubEventName === "pull_request" && ["opened", "closed", "reopened", "synchronize"].includes(action)) {
    const pr = payload.pull_request || {};
    const mappedAction = action === "synchronize" ? "updated" : action;
    const data = baseData(payload, pr);
    data.text = safeText(pr.body);
    data.head_sha = pr.head?.sha || null;
    return makeEvent(`github.pull_request.${mappedAction}`, `pr:${pr.id}:${action}:${pr.updated_at || ""}`, data, pr.updated_at || pr.created_at);
  }

  if (githubEventName === "pull_request_review" && action === "submitted") {
    const pr = payload.pull_request || {};
    const review = payload.review || {};
    const data = baseData(payload, pr);
    data.url = review.html_url || data.url;
    data.text = safeText(review.body);
    data.head_sha = pr.head?.sha || null;
    return makeEvent("github.pull_request_review.submitted", `review:${review.id}`, data, review.submitted_at);
  }

  if (githubEventName === "workflow_run" && action === "completed") {
    const run = payload.workflow_run || {};
    const data = baseData(payload, {});
    data.url = run.html_url || data.url;
    data.head_sha = run.head_sha || null;
    data.workflow = run.name || null;
    data.conclusion = run.conclusion || null;
    return makeEvent(
      "github.workflow_run.completed",
      `workflow:${run.id}:${run.run_attempt || 1}:${run.conclusion || ""}`,
      data,
      run.updated_at || run.created_at,
    );
  }

  return null;
}

function makeEvent(name, sourceIdentity, data, timestamp) {
  const eventId = `evt_${createHash("sha256").update(sourceIdentity).digest("base64url").slice(0, 32)}`;
  const event = {
    eventId,
    name,
    timestamp: normalizeTimestamp(timestamp),
    data,
    cursor: null,
  };
  const body = JSON.stringify(event);
  if (Buffer.byteLength(body, "utf8") > MAX_EVENT_BYTES) throw new Error("event_payload_too_large");
  return event;
}

function normalizeTimestamp(value) {
  const parsed = value ? new Date(value) : new Date();
  return Number.isNaN(parsed.getTime()) ? new Date().toISOString() : parsed.toISOString();
}

export function subscriptionMatches(subscription, event, nowMs = Date.now()) {
  if (!subscription || subscription.name !== event.name) return false;
  if (subscription.expiresAt && new Date(subscription.expiresAt).getTime() <= nowMs) return false;
  const args = subscription.arguments || {};
  if (args.repository !== event.data.repository) return false;
  if (args.number !== undefined && args.number !== event.data.number) return false;
  if (args.workflow !== undefined && args.workflow !== event.data.workflow) return false;
  return true;
}
