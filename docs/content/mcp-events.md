# MCP Events pilot

`agent-resources` exposes a modern MCP `2026-07-28` endpoint at:

`https://agent-resources-one.vercel.app/mcp`

The first rollout is deliberately narrow: public GitHub activity for `KAFKA2306/agent-resources` only. It does not expose private repository data or write tools.

## Event path

```text
GitHub event
→ GitHub Actions workflow
→ short-lived GitHub OIDC token
→ /api/github-events
→ matching persisted subscriptions
→ signed HTTPS callback
→ ChatGPT Work / dots event task
```

Supported events:

- `github.issue.opened`
- `github.issue.closed`
- `github.issue.reopened`
- `github.issue_comment.created`
- `github.pull_request.opened`
- `github.pull_request.updated`
- `github.pull_request.closed`
- `github.pull_request.reopened`
- `github.pull_request_review.submitted`
- `github.workflow_run.completed`

## Security boundaries

- MCP Events protocol version: `2026-07-28`.
- Persistent subscriptions use a private Vercel Blob store.
- Subscription creation fails closed while `BLOB_READ_WRITE_TOKEN` is unavailable.
- GitHub ingress accepts only GitHub Actions OIDC tokens with audience `agent-resources-mcp-events` from exactly `KAFKA2306/agent-resources`.
- Callback URLs must use HTTPS on port 443.
- DNS destinations are resolved before connection and private, local, reserved, or mixed public/private answers are rejected.
- Redirects are not followed.
- Deliveries use Standard Webhooks HMAC signatures and are capped at 256 KiB.
- User-authored issue, PR, review, and comment text is emitted as data, never as model instructions.
- Subscription IDs are deterministic and refreshes are idempotent.
- Signing-secret refresh keeps the previous key only for a short rotation window.

## Activation

The code is safe to deploy before storage exists. The GitHub emitter treats HTTP 503 from the ingress as dormant rather than a CI failure.

To activate subscriptions, attach a private Vercel Blob store to the `agent-resources` Vercel project so `BLOB_READ_WRITE_TOKEN` is available in Production. Then add the MCP endpoint as a personal ChatGPT plugin in developer mode and rescan its events.

Health probe:

`https://agent-resources-one.vercel.app/api/mcp-events-health`

`storageConfigured` must be `true` before `events/subscribe` can succeed.
