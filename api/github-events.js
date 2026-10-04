import { githubEventToMcp, subscriptionMatches } from "../dashboard/mcp-events-core.js";
import { bearerToken, PILOT_REPOSITORY, verifyGitHubActionsOidc } from "../dashboard/mcp-events-github.js";
import { BlobSubscriptionStore, StorageUnavailableError } from "../dashboard/mcp-events-store.js";
import { postSignedWebhook } from "../dashboard/mcp-events-webhook.js";

const store = new BlobSubscriptionStore();

function send(response, status, payload) {
  response.setHeader("Content-Type", "application/json; charset=utf-8");
  response.setHeader("Cache-Control", "no-store");
  return response.status(status).json(payload);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function deliverWithRetry(subscription, event) {
  const delays = [0, 250, 1_000];
  let lastStatus = 0;
  let lastError = null;
  for (let attempt = 0; attempt < delays.length; attempt += 1) {
    if (delays[attempt]) await sleep(delays[attempt]);
    try {
      const result = await postSignedWebhook(subscription, event);
      lastStatus = result.status;
      if (result.ok) return { ok: true, status: result.status, attempts: attempt + 1 };
      if (result.status === 410 || result.status === 413) break;
      if (result.status !== 429 && result.status < 500) break;
    } catch (error) {
      lastError = error?.message || String(error);
    }
  }
  return { ok: false, status: lastStatus, attempts: delays.length, error: lastError };
}

export default async function handler(request, response) {
  if (request.method !== "POST") return send(response, 405, { error: "method_not_allowed" });
  if (!store.configured()) return send(response, 503, { error: "mcp_events_storage_unavailable" });

  const token = bearerToken(request.headers.authorization);
  if (!token) return send(response, 401, { error: "missing_github_oidc_token" });
  let claims;
  try {
    claims = await verifyGitHubActionsOidc(token);
  } catch (error) {
    console.warn("mcp events rejected github oidc", error?.message || error);
    return send(response, 401, { error: "invalid_github_oidc_token" });
  }

  const githubEvent = request.headers["x-github-event"];
  const payload = request.body;
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return send(response, 400, { error: "invalid_github_event_payload" });
  }
  if (payload?.repository?.full_name !== claims.repository || claims.repository !== PILOT_REPOSITORY) {
    return send(response, 403, { error: "github_repository_mismatch" });
  }

  let event;
  try {
    event = githubEventToMcp(githubEvent, payload);
  } catch (error) {
    return send(response, 413, { error: error?.message || "event_payload_rejected" });
  }
  if (!event) return send(response, 202, { accepted: true, delivered: 0, ignored: true });

  try {
    const subscriptions = (await store.listSubscriptions()).filter((item) => subscriptionMatches(item, event));
    const results = [];
    for (const subscription of subscriptions) {
      results.push(await deliverWithRetry(subscription, event));
    }
    const delivered = results.filter((item) => item.ok).length;
    const failed = results.length - delivered;
    return send(response, failed ? 207 : 202, {
      accepted: true,
      eventId: event.eventId,
      matched: subscriptions.length,
      delivered,
      failed,
    });
  } catch (error) {
    if (error instanceof StorageUnavailableError) return send(response, 503, { error: "mcp_events_storage_unavailable" });
    console.error("mcp github event delivery failed", error?.message || error);
    return send(response, 500, { error: "mcp_events_delivery_failed" });
  }
}
