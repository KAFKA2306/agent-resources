import assert from "node:assert/strict";
import test from "node:test";
import { createHmac, generateKeyPairSync, sign } from "node:crypto";
import handler from "../../api/mcp.js";
import {
  McpAuthConfigurationError,
  authenticateMcpPrincipal,
  oauthConfiguration,
} from "../mcp-events-auth.js";
import {
  canonicalJson,
  deterministicSubscriptionId,
  githubEventToMcp,
  grantedExpiration,
  signStandardWebhook,
  subscriptionMatches,
  validateDelivery,
  validateSubscriptionArguments,
  validateWhsec,
} from "../mcp-events-core.js";
import { bearerToken, verifyGitHubActionsOidc } from "../mcp-events-github.js";
import { BlobSubscriptionStore } from "../mcp-events-store.js";
import { isPublicAddress, postSignedWebhook, resolvePublicDestination } from "../mcp-events-webhook.js";

const secret = `whsec_${Buffer.alloc(32, 7).toString("base64")}`;

function responseCapture() {
  const state = { status: 0, body: null, headers: {} };
  return {
    state,
    setHeader(name, value) { state.headers[name] = value; },
    status(value) { state.status = value; return this; },
    json(value) { state.body = value; return value; },
  };
}

function modernRequest(method, params = {}) {
  return {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "mcp-protocol-version": "2026-07-28",
      "mcp-method": method,
    },
    is: () => true,
    body: {
      jsonrpc: "2.0",
      id: 1,
      method,
      params: {
        ...params,
        _meta: {
          "io.modelcontextprotocol/protocolVersion": "2026-07-28",
          "io.modelcontextprotocol/clientCapabilities": {},
        },
      },
    },
  };
}

function fakeBlobClient() {
  const objects = new Map();
  return {
    objects,
    async put(pathname, body) {
      objects.set(pathname, String(body));
      return { pathname, url: `https://blob.invalid/${pathname}` };
    },
    async list({ prefix }) {
      return {
        blobs: [...objects.keys()]
          .filter((pathname) => pathname.startsWith(prefix))
          .map((pathname) => ({ pathname, url: `https://blob.invalid/${pathname}` })),
        cursor: undefined,
      };
    },
    async get(url) {
      const pathname = new URL(url).pathname.slice(1);
      const value = objects.get(pathname);
      return value == null ? null : { text: async () => value };
    },
    async del(pathname) { objects.delete(pathname); },
  };
}

let keySequence = 0;
function tokenFor(claimOverrides = {}) {
  const { privateKey, publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
  const jwk = publicKey.export({ format: "jwk" });
  keySequence += 1;
  jwk.kid = `test-key-${keySequence}`;
  jwk.use = "sig";
  jwk.alg = "RS256";
  const now = Math.floor(Date.now() / 1000);
  const header = Buffer.from(JSON.stringify({ alg: "RS256", typ: "JWT", kid: jwk.kid })).toString("base64url");
  const payload = Buffer.from(JSON.stringify({
    iss: "https://token.actions.githubusercontent.com",
    aud: "agent-resources-mcp-events",
    exp: now + 300,
    nbf: now - 10,
    repository: "KAFKA2306/agent-resources",
    repository_owner: "KAFKA2306",
    repository_visibility: "public",
    ...claimOverrides,
  })).toString("base64url");
  const signature = sign("RSA-SHA256", Buffer.from(`${header}.${payload}`), privateKey).toString("base64url");
  return {
    token: `${header}.${payload}.${signature}`,
    fetchImpl: async () => ({ ok: true, json: async () => ({ keys: [jwk] }) }),
  };
}

const rotationSecret = (value) => `whsec_${Buffer.alloc(32, value).toString("base64")}`;

function oauthTokenFor(claimOverrides = {}) {
  const { privateKey, publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
  const jwk = publicKey.export({ format: "jwk" });
  keySequence += 1;
  jwk.kid = `oauth-test-key-${keySequence}`;
  jwk.use = "sig";
  jwk.alg = "RS256";
  const now = Math.floor(Date.now() / 1000);
  const header = Buffer.from(JSON.stringify({ alg: "RS256", typ: "JWT", kid: jwk.kid })).toString("base64url");
  const payload = Buffer.from(JSON.stringify({
    iss: "https://auth.example.test/",
    aud: "https://agent-resources-one.vercel.app",
    exp: now + 300,
    nbf: now - 10,
    sub: "user_123",
    scope: "mcp.events",
    ...claimOverrides,
  })).toString("base64url");
  const signature = sign("RSA-SHA256", Buffer.from(`${header}.${payload}`), privateKey).toString("base64url");
  return {
    token: `${header}.${payload}.${signature}`,
    fetchImpl: async () => ({ ok: true, json: async () => ({ keys: [jwk] }) }),
    env: {
      MCP_EVENTS_OAUTH_ISSUER: "https://auth.example.test/",
      MCP_EVENTS_OAUTH_JWKS_URI: "https://auth.example.test/.well-known/jwks.json",
      MCP_EVENTS_OAUTH_AUDIENCE: "https://agent-resources-one.vercel.app",
      MCP_EVENTS_OAUTH_SCOPE: "mcp.events",
    },
  };
}

test("canonical JSON makes subscription identity independent of key order", () => {
  assert.equal(canonicalJson({ b: 2, a: 1 }), canonicalJson({ a: 1, b: 2 }));
  const left = deterministicSubscriptionId({ principal: "personal:kafka2306", callbackUrl: "https://example.com/callback", name: "github.issue.opened", arguments: { repository: "KAFKA2306/agent-resources", number: 381 } });
  const right = deterministicSubscriptionId({ principal: "personal:kafka2306", callbackUrl: "https://example.com/callback", name: "github.issue.opened", arguments: { number: 381, repository: "KAFKA2306/agent-resources" } });
  assert.equal(left, right);
});

test("whsec validation and Standard Webhooks signature follow the spec", () => {
  assert.equal(validateWhsec(secret), true);
  assert.equal(validateWhsec("whsec_bad"), false);
  const body = '{"hello":"world"}';
  const signature = signStandardWebhook(secret, "evt_123", 1700000000, body);
  assert.match(signature, /^v1,[A-Za-z0-9+/]+=*$/);
  assert.equal(signature, "v1," + createHmac("sha256", Buffer.alloc(32, 7)).update(`evt_123.1700000000.${body}`).digest("base64"));
});

test("subscription arguments are restricted to the pilot repository", () => {
  assert.deepEqual(validateSubscriptionArguments("github.issue.opened", { repository: "KAFKA2306/agent-resources" }), { ok: true });
  assert.equal(validateSubscriptionArguments("github.issue.opened", { repository: "someone/else" }).ok, false);
  assert.equal(validateSubscriptionArguments("github.issue.opened", { repository: "KAFKA2306/agent-resources", extra: true }).ok, false);
});

test("delivery requires HTTPS, port 443 and a valid whsec", () => {
  assert.equal(validateDelivery({ mode: "webhook", url: "https://example.com/cb", secret }).ok, true);
  assert.equal(validateDelivery({ mode: "webhook", url: "http://example.com/cb", secret }).ok, false);
  assert.equal(validateDelivery({ mode: "webhook", url: "https://example.com:8443/cb", secret }).ok, false);
});

test("GitHub issue comment maps to a stable MCP event and subscription filter", () => {
  const event = githubEventToMcp("issue_comment", {
    action: "created",
    repository: { full_name: "KAFKA2306/agent-resources", html_url: "https://github.com/KAFKA2306/agent-resources" },
    sender: { login: "kafka2306" },
    issue: { id: 1, number: 381, title: "Factory", html_url: "https://github.com/KAFKA2306/agent-resources/issues/381" },
    comment: { id: 99, body: "please fix", html_url: "https://github.com/KAFKA2306/agent-resources/issues/381#issuecomment-99", created_at: "2026-10-05T00:00:00Z" },
  });
  assert.equal(event.name, "github.issue_comment.created");
  assert.equal(event.data.number, 381);
  assert.equal(event.data.text, "please fix");
  assert.equal(subscriptionMatches({ name: "github.issue_comment.created", arguments: { repository: "KAFKA2306/agent-resources", number: 381 }, expiresAt: "2026-10-06T00:00:00Z" }, event, Date.parse("2026-10-05T00:01:00Z")), true);
});

test("subscription lifetime is bounded", () => {
  const now = Date.parse("2026-10-05T00:00:00Z");
  assert.equal(grantedExpiration(now, 1), "2026-10-05T01:00:00.000Z");
  assert.equal(grantedExpiration(now, 365 * 86400000), "2026-10-12T00:00:00.000Z");
});

test("server/discover advertises modern MCP and events", async () => {
  const response = responseCapture();
  await handler(modernRequest("server/discover"), response);
  assert.equal(response.state.status, 200);
  assert.deepEqual(response.state.body.result.supportedVersions, ["2026-07-28"]);
  assert.ok(response.state.body.result.capabilities.events);
});

test("events/list exposes the pilot catalog", async () => {
  const response = responseCapture();
  await handler(modernRequest("events/list"), response);
  assert.equal(response.state.status, 200);
  assert.ok(response.state.body.result.events.length >= 1);
  assert.equal(response.state.body.result.events[0].inputSchema.properties.repository.description.includes("agent-resources"), true);
});

test("protocol header mismatch fails with HTTP 400", async () => {
  const request = modernRequest("events/list");
  request.headers["mcp-protocol-version"] = "1900-01-01";
  const response = responseCapture();
  await handler(request, response);
  assert.equal(response.state.status, 400);
  assert.equal(response.state.body.error.code, -32023);
});

test("MCP event subscription auth fails closed when OAuth is not configured", async () => {
  assert.equal(oauthConfiguration({}).configured, false);
  await assert.rejects(
    () => authenticateMcpPrincipal({ headers: {} }, { env: {} }),
    McpAuthConfigurationError,
  );
});

test("MCP event subscription principal comes from a verified OAuth subject", async () => {
  const fixture = oauthTokenFor();
  const request = { headers: { authorization: `Bearer ${fixture.token}` } };
  const left = await authenticateMcpPrincipal(request, {
    env: fixture.env,
    fetchImpl: fixture.fetchImpl,
  });
  const right = await authenticateMcpPrincipal(request, {
    env: fixture.env,
    fetchImpl: fixture.fetchImpl,
  });
  assert.match(left, /^oauth_[A-Za-z0-9_-]{32}$/);
  assert.equal(left, right);
});

test("MCP event subscription auth rejects a token for another resource", async () => {
  const fixture = oauthTokenFor({ aud: "https://wrong.example.test" });
  await assert.rejects(
    () => authenticateMcpPrincipal(
      { headers: { authorization: `Bearer ${fixture.token}` } },
      { env: fixture.env, fetchImpl: fixture.fetchImpl },
    ),
    /oauth_bad_audience/,
  );
});

test("github actions oidc accepts exact pilot repository and audience", async () => {
  const fixture = tokenFor();
  const claims = await verifyGitHubActionsOidc(fixture.token, { fetchImpl: fixture.fetchImpl });
  assert.equal(claims.repository, "KAFKA2306/agent-resources");
});

test("github actions oidc rejects another repository", async () => {
  const fixture = tokenFor({ repository: "KAFKA2306/other" });
  await assert.rejects(() => verifyGitHubActionsOidc(fixture.token, { fetchImpl: fixture.fetchImpl }), /repository_not_allowed/);
});

test("bearer parser is strict enough for ingress", () => {
  assert.equal(bearerToken("Bearer abc.def.ghi"), "abc.def.ghi");
  assert.equal(bearerToken("Basic abc"), null);
});

test("blob store keeps one durable object per deterministic subscription", async () => {
  const client = fakeBlobClient();
  const store = new BlobSubscriptionStore({ clientLoader: async () => client });
  await store.putSubscription({ id: "sub_1", name: "github.issue.opened" });
  await store.putSubscription({ id: "sub_1", name: "github.issue.closed" });
  const values = await store.listSubscriptions();
  assert.equal(values.length, 1);
  assert.equal(values[0].name, "github.issue.closed");
  await store.deleteSubscription("sub_1");
  assert.equal((await store.listSubscriptions()).length, 0);
});

test("verification cache is keyed by principal and callback", async () => {
  const client = fakeBlobClient();
  const store = new BlobSubscriptionStore({ clientLoader: async () => client });
  await store.putVerification("p", "https://example.com/cb", "2026-10-05T01:00:00Z");
  const cached = await store.getVerification("p", "https://example.com/cb");
  assert.equal(cached.principal, "p");
  assert.equal(cached.callbackUrl, "https://example.com/cb");
});

test("callback address filtering blocks local and private ranges", () => {
  assert.equal(isPublicAddress("127.0.0.1", 4), false);
  assert.equal(isPublicAddress("10.2.3.4", 4), false);
  assert.equal(isPublicAddress("169.254.169.254", 4), false);
  assert.equal(isPublicAddress("8.8.8.8", 4), true);
  assert.equal(isPublicAddress("::1", 6), false);
  assert.equal(isPublicAddress("2606:4700:4700::1111", 6), true);
});

test("DNS resolution rejects a hostname if any answer is non-public", async () => {
  await assert.rejects(() => resolvePublicDestination("example.test", async () => [{ address: "8.8.8.8", family: 4 }, { address: "127.0.0.1", family: 4 }]), /callback_address_not_public/);
});

test("delivery signs with new and previous secret during rotation window", async () => {
  let headers;
  const subscription = { id: "sub_rotation", url: "https://example.com/callback", secret: rotationSecret(1), previousSecret: rotationSecret(2), previousSecretUntil: new Date(Date.now() + 60_000).toISOString() };
  await postSignedWebhook(subscription, { eventId: "evt_rotation", name: "x", timestamp: new Date().toISOString(), data: {}, cursor: null }, async (_url, options) => {
    headers = options.headers;
    return { ok: true, status: 202 };
  });
  assert.equal(headers["webhook-signature"].split(" ").length, 2);
});
