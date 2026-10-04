import dns from "node:dns/promises";
import https from "node:https";
import net from "node:net";
import { signStandardWebhook } from "./mcp-events-core.js";

const blocked = new net.BlockList();
for (const [network, prefix, type] of [
  ["0.0.0.0", 8, "ipv4"],
  ["10.0.0.0", 8, "ipv4"],
  ["100.64.0.0", 10, "ipv4"],
  ["127.0.0.0", 8, "ipv4"],
  ["169.254.0.0", 16, "ipv4"],
  ["172.16.0.0", 12, "ipv4"],
  ["192.0.0.0", 24, "ipv4"],
  ["192.0.2.0", 24, "ipv4"],
  ["192.168.0.0", 16, "ipv4"],
  ["198.18.0.0", 15, "ipv4"],
  ["198.51.100.0", 24, "ipv4"],
  ["203.0.113.0", 24, "ipv4"],
  ["224.0.0.0", 4, "ipv4"],
  ["240.0.0.0", 4, "ipv4"],
  ["::", 128, "ipv6"],
  ["::1", 128, "ipv6"],
  ["fc00::", 7, "ipv6"],
  ["fe80::", 10, "ipv6"],
  ["ff00::", 8, "ipv6"],
  ["2001:db8::", 32, "ipv6"],
]) blocked.addSubnet(network, prefix, type);

export function isPublicAddress(address, family) {
  const normalizedFamily = family === 6 || family === "IPv6" ? "ipv6" : "ipv4";
  if (!net.isIP(address)) return false;
  return !blocked.check(address, normalizedFamily);
}

export async function resolvePublicDestination(hostname, lookup = dns.lookup) {
  if (net.isIP(hostname)) {
    const family = net.isIP(hostname);
    if (!isPublicAddress(hostname, family)) throw new Error("callback_address_not_public");
    return { address: hostname, family };
  }
  const answers = await lookup(hostname, { all: true, verbatim: true });
  if (!Array.isArray(answers) || answers.length === 0) throw new Error("callback_dns_empty");
  if (answers.some((answer) => !isPublicAddress(answer.address, answer.family))) {
    throw new Error("callback_address_not_public");
  }
  return answers[0];
}

export async function safeWebhookFetch(urlString, options = {}, deps = {}) {
  const url = new URL(urlString);
  if (url.protocol !== "https:" || url.username || url.password || (url.port && url.port !== "443")) {
    throw new Error("invalid_callback_url");
  }
  const resolved = await resolvePublicDestination(url.hostname, deps.lookup || dns.lookup);
  const requestImpl = deps.request || https.request;
  const body = options.body == null ? Buffer.alloc(0) : Buffer.from(options.body);
  const headers = { ...(options.headers || {}), Host: url.host, "Content-Length": String(body.length) };
  const timeoutMs = options.timeoutMs || 10_000;

  return await new Promise((resolve, reject) => {
    const request = requestImpl(
      {
        protocol: "https:",
        hostname: url.hostname,
        port: 443,
        path: `${url.pathname}${url.search}`,
        method: options.method || "GET",
        servername: url.hostname,
        headers,
        lookup: (_hostname, _options, callback) => callback(null, resolved.address, resolved.family),
        timeout: timeoutMs,
      },
      (response) => {
        const chunks = [];
        let size = 0;
        response.on("data", (chunk) => {
          size += chunk.length;
          if (size > 64 * 1024) {
            response.destroy(new Error("callback_response_too_large"));
            return;
          }
          chunks.push(chunk);
        });
        response.on("end", () => {
          const raw = Buffer.concat(chunks).toString("utf8");
          resolve({
            ok: response.statusCode >= 200 && response.statusCode < 300,
            status: response.statusCode || 0,
            text: async () => raw,
            json: async () => JSON.parse(raw || "{}"),
          });
        });
        response.on("error", reject);
      },
    );
    request.on("timeout", () => request.destroy(new Error("callback_timeout")));
    request.on("error", reject);
    if (body.length) request.write(body);
    request.end();
  });
}

export async function postSignedWebhook(subscription, payload, webhookFetch = safeWebhookFetch, explicitWebhookId = null) {
  const body = JSON.stringify(payload);
  if (Buffer.byteLength(body, "utf8") > 256 * 1024) throw new Error("event_payload_too_large");
  const timestamp = Math.floor(Date.now() / 1000);
  const webhookId = explicitWebhookId || payload.eventId || payload.webhookId;
  if (!webhookId) throw new Error("missing_webhook_id");
  const signatures = [signStandardWebhook(subscription.secret, webhookId, timestamp, body)];
  if (
    subscription.previousSecret &&
    subscription.previousSecretUntil &&
    new Date(subscription.previousSecretUntil).getTime() > Date.now()
  ) {
    signatures.push(signStandardWebhook(subscription.previousSecret, webhookId, timestamp, body));
  }
  return webhookFetch(subscription.url, {
    method: "POST",
    timeoutMs: 10_000,
    headers: {
      "Content-Type": "application/json",
      "webhook-id": webhookId,
      "webhook-timestamp": String(timestamp),
      "webhook-signature": signatures.join(" "),
      "X-MCP-Subscription-Id": subscription.id,
    },
    body,
  });
}
