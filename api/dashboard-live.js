import {
  LIVE_CACHE_SECONDS,
  LIVE_STALE_WHILE_REVALIDATE_SECONDS,
  LiveDataError,
  collectLiveState,
} from "../dashboard/live-core.js";

let memoryCache = null;

function setCommonHeaders(response) {
  response.setHeader("Content-Type", "application/json; charset=utf-8");
  response.setHeader("Access-Control-Allow-Origin", "*");
  response.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  response.setHeader("Access-Control-Allow-Headers", "Content-Type");
  response.setHeader("Cache-Control", "no-store, max-age=0");
  response.setHeader(
    "Vercel-CDN-Cache-Control",
    `public, max-age=${LIVE_CACHE_SECONDS}, stale-while-revalidate=${LIVE_STALE_WHILE_REVALIDATE_SECONDS}`,
  );
}

function send(response, status, payload) {
  setCommonHeaders(response);
  return response.status(status).json(payload);
}

export default async function handler(request, response) {
  if (request.method === "OPTIONS") {
    setCommonHeaders(response);
    return response.status(204).end();
  }
  if (request.method !== "GET") return send(response, 405, { error: "method_not_allowed" });
  if (request.url && new URL(request.url, "https://dashboard.invalid").search) {
    return send(response, 400, { error: "query_parameters_not_supported" });
  }

  const now = Date.now();
  if (memoryCache && now - memoryCache.createdAt < LIVE_CACHE_SECONDS * 1000) {
    response.setHeader("X-Agent-Resources-Live-Cache", "memory-hit");
    return send(response, 200, memoryCache.payload);
  }

  try {
    const payload = await collectLiveState({
      token: process.env.DASHBOARD_GITHUB_TOKEN,
      fetchImpl: globalThis.fetch,
      now: new Date(now),
    });
    memoryCache = { createdAt: now, payload };
    response.setHeader("X-Agent-Resources-Live-Cache", "origin-refresh");
    return send(response, 200, payload);
  } catch (error) {
    const known = error instanceof LiveDataError;
    const code = known ? error.code : "live_endpoint_error";
    const status = code === "missing_server_credential" ? 503 : code === "github_rate_limited" ? 503 : 502;
    console.error("dashboard live endpoint failed", code, known ? error.details : error);
    return send(response, status, {
      error: code,
      stale: true,
      fetchedAt: null,
      retryAfter: known ? error.details?.retryAfter || null : null,
    });
  }
}
