import { oauthConfiguration } from "../dashboard/mcp-events-auth.js";\nimport { EVENT_DEFINITIONS, MCP_PROTOCOL_VERSION } from "../dashboard/mcp-events-core.js";
import { BlobSubscriptionStore } from "../dashboard/mcp-events-store.js";

const store = new BlobSubscriptionStore();

export default async function handler(request, response) {
  if (request.method !== "GET") return response.status(405).json({ error: "method_not_allowed" });
  response.setHeader("Cache-Control", "no-store");
  return response.status(200).json({
    service: "agent-resources-mcp-events",
    protocolVersion: MCP_PROTOCOL_VERSION,
    storageConfigured: await store.available(),\n    oauthConfigured: oauth.configured,\n    oauthResource: oauth.resource,
    pilotRepository: "KAFKA2306/agent-resources",
    eventCount: EVENT_DEFINITIONS.length,
  });
}
