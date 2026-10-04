import { verificationCacheKey } from "./mcp-events-core.js";

const SUBSCRIPTION_PREFIX = "mcp-events/subscriptions/";
const VERIFICATION_PREFIX = "mcp-events/verifications/";

export class StorageUnavailableError extends Error {
  constructor(message = "persistent MCP Events storage is not configured") {
    super(message);
    this.name = "StorageUnavailableError";
  }
}

async function defaultBlobClient() {
  if (!process.env.BLOB_READ_WRITE_TOKEN) throw new StorageUnavailableError();
  return import("@vercel/blob");
}

async function readJsonBlob(client, blob) {
  const response = await client.get(blob.url, { access: "private" });
  if (!response) return null;
  return JSON.parse(await response.text());
}

async function listAll(client, prefix) {
  const blobs = [];
  let cursor;
  do {
    const page = await client.list({ prefix, limit: 100, cursor });
    blobs.push(...page.blobs);
    cursor = page.cursor || undefined;
  } while (cursor);
  return blobs;
}

export class BlobSubscriptionStore {
  constructor({ clientLoader = defaultBlobClient } = {}) {
    this.clientLoader = clientLoader;
  }

  configured() {
    return Boolean(process.env.BLOB_READ_WRITE_TOKEN);
  }

  async putSubscription(subscription) {
    const client = await this.clientLoader();
    const pathname = `${SUBSCRIPTION_PREFIX}${subscription.id}.json`;
    await client.put(pathname, JSON.stringify(subscription), {
      access: "private",
      addRandomSuffix: false,
      allowOverwrite: true,
      contentType: "application/json",
      cacheControlMaxAge: 60,
    });
  }

  async deleteSubscription(id) {
    const client = await this.clientLoader();
    await client.del(`${SUBSCRIPTION_PREFIX}${id}.json`);
  }

  async listSubscriptions() {
    const client = await this.clientLoader();
    const blobs = await listAll(client, SUBSCRIPTION_PREFIX);
    const subscriptions = [];
    for (const blob of blobs) {
      try {
        const value = await readJsonBlob(client, blob);
        if (value) subscriptions.push(value);
      } catch (error) {
        console.warn("mcp events ignored unreadable subscription", blob.pathname, error?.message || error);
      }
    }
    return subscriptions;
  }

  async getVerification(principal, callbackUrl) {
    const client = await this.clientLoader();
    const key = verificationCacheKey({ principal, callbackUrl });
    const pathname = `${VERIFICATION_PREFIX}${key}.json`;
    const blobs = await listAll(client, pathname);
    const blob = blobs.find((entry) => entry.pathname === pathname);
    return blob ? readJsonBlob(client, blob) : null;
  }

  async putVerification(principal, callbackUrl, verifiedUntil) {
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
  }
}
