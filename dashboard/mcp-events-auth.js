import { createHash, createPublicKey, verify as verifySignature } from "node:crypto";

const JWKS_CACHE_MS = 15 * 60 * 1000;
const DEFAULT_RESOURCE = "https://agent-resources-one.vercel.app";
const DEFAULT_SCOPE = "mcp.events";
const jwksCache = new Map();

export class McpAuthConfigurationError extends Error {
  constructor(message = "MCP Events OAuth is not configured") {
    super(message);
    this.name = "McpAuthConfigurationError";
  }
}

export class McpAuthenticationError extends Error {
  constructor(message = "invalid access token") {
    super(message);
    this.name = "McpAuthenticationError";
  }
}

export function oauthConfiguration(env = process.env) {
  const resource = String(env.MCP_EVENTS_RESOURCE || DEFAULT_RESOURCE).replace(/\/$/, "");
  const issuer = String(env.MCP_EVENTS_OAUTH_ISSUER || "").trim();
  const jwksUrl = String(env.MCP_EVENTS_OAUTH_JWKS_URI || "").trim();
  const audience = String(env.MCP_EVENTS_OAUTH_AUDIENCE || resource).trim();
  const scope = String(env.MCP_EVENTS_OAUTH_SCOPE || DEFAULT_SCOPE).trim();
  return {
    resource,
    issuer,
    jwksUrl,
    audience,
    scope,
    configured: Boolean(issuer && jwksUrl && audience),
  };
}

export function protectedResourceMetadata(env = process.env) {
  const config = oauthConfiguration(env);
  if (!config.configured) throw new McpAuthConfigurationError();
  return {
    resource: config.resource,
    authorization_servers: [config.issuer],
    scopes_supported: config.scope ? [config.scope] : [],
  };
}

export function authenticationChallenge(env = process.env) {
  const config = oauthConfiguration(env);
  const metadataUrl = `${config.resource}/.well-known/oauth-protected-resource`;
  return `Bearer resource_metadata="${metadataUrl}"${config.scope ? `, scope="${config.scope}"` : ""}`;
}

function bearerToken(value) {
  if (typeof value !== "string") return null;
  const match = /^Bearer\s+(.+)$/i.exec(value.trim());
  return match ? match[1] : null;
}

function decodeBase64Url(value) {
  return Buffer.from(String(value), "base64url");
}

function decodeJson(value) {
  return JSON.parse(decodeBase64Url(value).toString("utf8"));
}

function audienceMatches(actual, expected) {
  return typeof actual === "string"
    ? actual === expected
    : Array.isArray(actual) && actual.includes(expected);
}

function scopeMatches(claims, requiredScope) {
  if (!requiredScope) return true;
  const scopes = new Set();
  if (typeof claims.scope === "string") {
    for (const item of claims.scope.split(/\s+/).filter(Boolean)) scopes.add(item);
  }
  if (typeof claims.scp === "string") {
    for (const item of claims.scp.split(/\s+/).filter(Boolean)) scopes.add(item);
  } else if (Array.isArray(claims.scp)) {
    for (const item of claims.scp) if (typeof item === "string") scopes.add(item);
  }
  return scopes.has(requiredScope);
}

async function loadJwks(url, fetchImpl, nowMs, forceRefresh = false) {
  const cached = jwksCache.get(url);
  if (!forceRefresh && cached && nowMs < cached.expiresAt) return cached.value;
  const response = await fetchImpl(url, {
    headers: { Accept: "application/json" },
    signal: AbortSignal.timeout(5_000),
  });
  if (!response.ok) throw new McpAuthenticationError(`oauth_jwks_${response.status}`);
  const value = await response.json();
  if (!Array.isArray(value?.keys)) throw new McpAuthenticationError("oauth_invalid_jwks");
  jwksCache.set(url, { value, expiresAt: nowMs + JWKS_CACHE_MS });
  return value;
}

function principalFromClaims(issuer, subject) {
  const digest = createHash("sha256")
    .update(`${issuer}\n${subject}`)
    .digest("base64url")
    .slice(0, 32);
  return `oauth_${digest}`;
}

export async function authenticateMcpPrincipal(
  request,
  { env = process.env, fetchImpl = globalThis.fetch, nowMs = Date.now() } = {},
) {
  const config = oauthConfiguration(env);
  if (!config.configured) throw new McpAuthConfigurationError();

  const token = bearerToken(request?.headers?.authorization);
  if (!token || token.split(".").length !== 3) throw new McpAuthenticationError("missing_or_invalid_bearer_token");

  const [encodedHeader, encodedPayload, encodedSignature] = token.split(".");
  let header;
  let claims;
  try {
    header = decodeJson(encodedHeader);
    claims = decodeJson(encodedPayload);
  } catch {
    throw new McpAuthenticationError("invalid_access_token");
  }
  if (header.alg !== "RS256" || typeof header.kid !== "string") {
    throw new McpAuthenticationError("unsupported_access_token");
  }

  let jwks = await loadJwks(config.jwksUrl, fetchImpl, nowMs);
  let jwk = jwks.keys.find((candidate) => candidate.kid === header.kid && candidate.kty === "RSA");
  if (!jwk) {
    jwks = await loadJwks(config.jwksUrl, fetchImpl, nowMs, true);
    jwk = jwks.keys.find((candidate) => candidate.kid === header.kid && candidate.kty === "RSA");
  }
  if (!jwk) throw new McpAuthenticationError("oauth_unknown_key");

  let signatureOk = false;
  try {
    const key = createPublicKey({ key: jwk, format: "jwk" });
    signatureOk = verifySignature(
      "RSA-SHA256",
      Buffer.from(`${encodedHeader}.${encodedPayload}`),
      key,
      decodeBase64Url(encodedSignature),
    );
  } catch {
    signatureOk = false;
  }
  if (!signatureOk) throw new McpAuthenticationError("oauth_bad_signature");

  const nowSeconds = Math.floor(nowMs / 1000);
  if (claims.iss !== config.issuer) throw new McpAuthenticationError("oauth_bad_issuer");
  if (!audienceMatches(claims.aud, config.audience)) throw new McpAuthenticationError("oauth_bad_audience");
  if (!Number.isFinite(claims.exp) || claims.exp < nowSeconds - 30) throw new McpAuthenticationError("oauth_expired");
  if (Number.isFinite(claims.nbf) && claims.nbf > nowSeconds + 30) throw new McpAuthenticationError("oauth_not_yet_valid");
  if (typeof claims.sub !== "string" || !claims.sub.trim()) throw new McpAuthenticationError("oauth_missing_subject");
  if (!scopeMatches(claims, config.scope)) throw new McpAuthenticationError("oauth_insufficient_scope");

  return principalFromClaims(config.issuer, claims.sub);
}
