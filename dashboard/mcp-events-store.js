import { verificationCacheKey } from "./mcp-events-core.js";

const SUBSCRIPTION_PREFIX = "mcp-events/subscriptions/";
const VERIFICATION_PREFIX = "mcp-events/verifications/";

export class StorageUnavailableError extends Error {
  constructor(message = "persistent MCP Events storage is not configured") {
    super(message);
    this.name = "StorageUnavailableError";
  }
}

function asStorageUnavailable(error) {
  return error instanceof StorageUnavailableError
    ? error
    : new StorageUnavailableError(error?.message || String(error));
}

async function defaultBlobClient() {
  try {
    return await import("@vercel/blob");
  } catch (error) {
    throw asStorageUnavailable(error);
  }
}

async function readJsonBlob(client, blob) {
  let response;
  try {
    response = await client.get(blob.url, { access: "private", useCache: false });
  } catch (error) {
    throw asStorageUnavailable(error);
  }
  if (!response) return null;
  if (typeof response.text === "function") return JSON.parse(await response.text());
  return JSON.parse(await new Response(response.stream).text());
}

async function listAll(client, prefix) {
  const blobs = [];
  let cursor;
  try {
    do {
      const page = await client.list({ prefix, limit: 100, cursor });
      blobs.push(...page.blobs);
      cursor = page.cursor || undefined;
    } while (cursor);
  } catch (error) {
    throw asStorageUnavailable(error);
  }
  return blobs;
}

export class BlobSubscriptionStore {
  constructor({ clientLoader = defaultBlobClient } = {}) {
    this.clientLoader = clientLoader;
  }

  async available() {
    try {
      await this.listSubscriptions();
      return true;
    } catch {
      return false;
    }
  }

  async putSubscription(subscription) {
    try {
      const client = await this.clientLoader();
      const pathname = `${SUBSCRIPTION_PREFIX}${subscription.id}.json`;
      await client.put(pathname, JSON.stringify(subscription), {
        access: "private",
        addRandomSuffix: false,
        allowOverwrite: true,
        contentType: "application/json",
        cacheControlMaxAge: 60,
      });
    } catch (error) {
      throw asStorageUnavailable(error);
    }
  }

  async deleteSubscription(id) {
    try {
      const client = await this.clientLoader();
      await client.del(`${SUBSCRIPTION_PREFIX}${id}.json`);
    } catch (error) {
      throw asStorageUnavailable(error);
    }
  }

  async listSubscriptions() {
    let client;
    try {
      client = await this.clientLoader();
    } catch (error) {
      throw asStorageUnavailable(error);
    }
    const blobs = await listAll(client, SUBSCRIPTION_PREFIX);
    const subscriptions = [];
    for (const blob of blobs) {
      try {
        const value = await readJsonBlob(client, blob);
        if (value) subscriptions.push(value);
      } catch (error) {
        if (error instanceof StorageUnavailableError) throw error;
        console.warn("mcp events ignored unreadable subscription", blob.pathname, error?.message || error);
      }
    }
    return subscriptions;
  }

  async getVerification(principal, callbackUrl) {
    let client;
    try {
      client = await this.clientLoader();
    } catch (error) {
      throw asStorageUnavailable(error);
    }
    const key = verificationCacheKey({ principal, callbackUrl });
    const pathname = `${VERIFICATION_PREFIX}${key}.json`;
    const blobs = await listAll(client, pathname);
    const blob = blobs.find((entry) => entry.pathname === pathname);
    return blob ? readJsonBlob(client, blob) : null;
  }

  async putVerification(principal, callbackUrl, verifiedUntil) {
    try {
      const client = await this.clientLoader();
      const key = verificationCacheKey({ principal, callbackUrl });
      await client.put(
        `${VERIFICATION_PREFIX}${key}.json`,
        JSON.stringify({ principal, callbackUrl, verifiedUntil }),
        {
          access: "private",
          addRandomSuffix: false,
          allowOverwrite: true,
          contentType: "application/json",
          cacheControlMaxAge: 60,
        },
      );
    } catch (error) {
      throw asStorageUnavailable(error);
    }
  }
}
