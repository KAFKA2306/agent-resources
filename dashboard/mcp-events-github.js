import { createPublicKey, verify as verifySignature } from "node:crypto";

const ISSUER = "https://token.actions.githubusercontent.com";
export const GITHUB_OIDC_AUDIENCE = "agent-resources-mcp-events";
export const PILOT_REPOSITORY = "KAFKA2306/agent-resources";
const JWKS_URL = `${ISSUER}/.well-known/jwks`;
const JWKS_CACHE_MS = 15 * 60 * 1000;
let jwksCache = null;

function decodeBase64Url(value) {
  return Buffer.from(String(value), "base64url");
}

function decodeJson(value) {
  return JSON.parse(decodeBase64Url(value).toString("utf8"));
}

function audienceMatches(aud, expected) {
  return typeof aud === "string" ? aud === expected : Array.isArray(aud) && aud.includes(expected);
}

async function loadJwks(fetchImpl = globalThis.fetch, nowMs = Date.now(), forceRefresh = false) {
  if (!forceRefresh && jwksCache && nowMs < jwksCache.expiresAt) return jwksCache.value;
  const response = await fetchImpl(JWKS_URL, {
    headers: { Accept: "application/json" },
    signal: AbortSignal.timeout(5_000),
  });
  if (!response.ok) throw new Error(`github_oidc_jwks_${response.status}`);
  const value = await response.json();
  if (!Array.isArray(value?.keys)) throw new Error("github_oidc_invalid_jwks");
  jwksCache = { value, expiresAt: nowMs + JWKS_CACHE_MS };
  return value;
}

export async function verifyGitHubActionsOidc(
  token,
  {
    fetchImpl = globalThis.fetch,
    nowMs = Date.now(),
    audience = GITHUB_OIDC_AUDIENCE,
    repository = PILOT_REPOSITORY,
  } = {},
) {
  if (typeof token !== "string" || token.split(".").length !== 3) {
    throw new Error("github_oidc_invalid_token");
  }
  const [encodedHeader, encodedPayload, encodedSignature] = token.split(".");
  let header;
  let claims;
  try {
    header = decodeJson(encodedHeader);
    claims = decodeJson(encodedPayload);
  } catch {
    throw new Error("github_oidc_invalid_token");
  }
  if (header.alg !== "RS256" || typeof header.kid !== "string") {
    throw new Error("github_oidc_invalid_header");
  }

  let jwks = await loadJwks(fetchImpl, nowMs);
  let jwk = jwks.keys.find((candidate) => candidate.kid === header.kid && candidate.kty === "RSA");
  if (!jwk) {
    jwks = await loadJwks(fetchImpl, nowMs, true);
    jwk = jwks.keys.find((candidate) => candidate.kid === header.kid && candidate.kty === "RSA");
  }
  if (!jwk) throw new Error("github_oidc_unknown_key");

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
  if (!signatureOk) throw new Error("github_oidc_bad_signature");

  const nowSeconds = Math.floor(nowMs / 1000);
  if (claims.iss !== ISSUER) throw new Error("github_oidc_bad_issuer");
  if (!audienceMatches(claims.aud, audience)) throw new Error("github_oidc_bad_audience");
  if (!Number.isFinite(claims.exp) || claims.exp < nowSeconds - 30) throw new Error("github_oidc_expired");
  if (Number.isFinite(claims.nbf) && claims.nbf > nowSeconds + 30) throw new Error("github_oidc_not_yet_valid");
  if (claims.repository !== repository || claims.repository_owner !== "KAFKA2306") {
    throw new Error("github_oidc_repository_not_allowed");
  }
  if (claims.repository_visibility && claims.repository_visibility !== "public") {
    throw new Error("github_oidc_repository_not_public");
  }
  return claims;
}

export function bearerToken(headerValue) {
  if (typeof headerValue !== "string") return null;
  const match = /^Bearer\s+(.+)$/i.exec(headerValue.trim());
  return match ? match[1] : null;
}
