# Dashboard live data plane

The public dashboard separates static UI deployment from volatile GitHub state.

## Data flow

1. GitHub Pages loads `docs/dashboard/dashboard.json` as a validated public-only baseline.
2. The browser resolves a live endpoint from `docs/dashboard/live-config.json` (or `/api/dashboard-live` when the UI itself is served by Vercel).
3. The live endpoint reads current public repositories, open Issue/PR state, latest workflow run per repository, and recent Issue/PR activity from GitHub REST.
4. The browser overlays only volatile `repositories`, `workItems`, and `activity`. Heavy monthly stats remain from the baseline snapshot.
5. If the live endpoint is missing, stale, rate-limited, or invalid, the browser keeps the baseline and displays `SNAPSHOT FALLBACK` or `STALE`; it never labels stale data as live.

## Credential boundary

`api/dashboard-live.js` requires `DASHBOARD_GITHUB_TOKEN` in the server-side deployment environment. The token is never returned by the endpoint, copied into the static Pages artifact, or stored in repository files.

The token only needs read access required for public repository metadata, Issue/PR search, and GitHub Actions workflow runs.

## Cache and request budget

The live response uses a 120-second Vercel CDN max-age plus a 30-second stale-while-revalidate window. A cache miss performs:

- repository list pagination (normally two requests at the current repository count),
- one or more open Issue/PR search requests,
- up to two recent-activity search requests,
- one latest workflow-run request for each public non-archived repository.

The response exposes `requestBudget` and rate-limit metadata, without exposing credentials. The 120-second floor is deliberate: at roughly 127 public repositories, a full refresh every 60 seconds would exceed a normal authenticated GitHub REST primary budget. The endpoint fails closed on upstream 403/429 or partial/invalid responses.

## Public-only contract

The live layer retains the same boundary as the canonical snapshot:

- owner must be `KAFKA2306`,
- repositories must be public,
- archived/private repositories are excluded,
- work items and activity are accepted only when their `repositoryId` belongs to the returned public repository set,
- `agent-zone-*` repository topics remain the only semantic zone source.

## Production provisioning

Until a verified production function URL exists, `docs/dashboard/live-config.json` keeps `endpoint: null`. GitHub Pages therefore remains truthful and shows `SNAPSHOT FALLBACK` rather than attempting an unverified URL.

To enable live reads on GitHub Pages:

1. provision the server-side project containing `api/dashboard-live.js`,
2. set `DASHBOARD_GITHUB_TOKEN` in that server-side environment,
3. verify `/api/dashboard-live` returns a public-only payload and acceptable `requestBudget`,
4. set the verified HTTPS URL in `docs/dashboard/live-config.json`,
5. run the production browser smoke test.

After that one-time configuration, page opens and tab returns refresh through the live endpoint; Pages rebuilds are no longer the freshness path.
