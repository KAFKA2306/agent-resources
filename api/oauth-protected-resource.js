import {
  McpAuthConfigurationError,
  protectedResourceMetadata,
} from "../dashboard/mcp-events-auth.js";

export default async function handler(request, response) {
  if (request.method !== "GET") return response.status(405).json({ error: "method_not_allowed" });
  response.setHeader("Cache-Control", "no-store");
  try {
    return response.status(200).json(protectedResourceMetadata());
  } catch (error) {
    if (error instanceof McpAuthConfigurationError) {
      return response.status(503).json({ error: "mcp_events_oauth_not_configured" });
    }
    console.error("mcp oauth metadata failed", error?.message || error);
    return response.status(500).json({ error: "mcp_events_oauth_metadata_failed" });
  }
}
