import {
  LIVE_CACHE_SECONDS,
  LIVE_STALE_WHILE_REVALIDATE_SECONDS,
  LiveDataError,
  collectLiveState,
} from "../dashboard/live-core.js";

const CONDITIONAL_CACHE_MAX_ENTRIES = 512;
let memoryCache = null;
const conditionalCache = new Map();

function rememberConditionalResponse(cache, key, value) {
  if (cache.has(key)) cache.delete(key);
  while (cache.size >= CONDITIONAL_CACHE_MAX_ENTRIES) {
    const oldest = cache.keys().next().value;
    if (oldest === undefined) break;
    cache.delete(oldest);
  }
  cache.set(key, value);
}

export function createConditionalFetch(fetchImpl, cache = new Map(), stats = {}) {
  if (typeof fetchImpl !== "function") throw new TypeError("fetchImpl must be a function");
  stats.conditionalRequestCount ??= 0;
  stats.notModifiedRequestCount ??= 0;

  return async (url, options = {}) => {
    const key = String(url);
    const cached = cache.get(key);
    const headers = new Headers(options.headers || {});
    if (cached?.etag) {
      headers.set("If-None-Match", cached.etag);
      stats.conditionalRequestCount += 1;
    }

    const response = await fetchImpl(url, { ...options, headers });
    if (response.status === 304 && cached) {
      stats.notModifiedRequestCount += 1;
      return new Response(JSON.stringify(cached.payload), {
        status: 200,
        headers: response.headers,
      });
    }

    if (response.ok) {
      const etag = response.headers?.get?.("etag");
      if (etag && typeof response.clone === "function") {
        try {
          const payload = await response.clone().json();
          rememberConditionalResponse(cache, key, { etag, payload });
        } catch (error) {
          console.warn("dashboard live conditional cache skipped invalid JSON", error);
        }
      }
    }
    return response;
  };
}

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
    const conditionalStats = { conditionalRequestCount: 0, notModifiedRequestCount: 0 };
    const payload = await collectLiveState({
      token: process.env.DASHBOARD_GITHUB_TOKEN,
      fetchImpl: createConditionalFetch(globalThis.fetch, conditionalCache, conditionalStats),
      now: new Date(now),
    });
    const primaryRateChargedRequestCount = Math.max(
      0,
      payload.requestBudget.requestCount - conditionalStats.notModifiedRequestCount,
    );
    payload.requestBudget = {
      ...payload.requestBudget,
      conditionalRequestCount: conditionalStats.conditionalRequestCount,
      notModifiedRequestCount: conditionalStats.notModifiedRequestCount,
      primaryRateChargedRequestCount,
      conditionalCacheEntries: conditionalCache.size,
      theoreticalPrimaryRateChargedRequestsPerHourAtObserved304Rate:
        Math.ceil(3600 / LIVE_CACHE_SECONDS) * primaryRateChargedRequestCount,
    };
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
