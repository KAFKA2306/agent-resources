# Dashboard live data plane

The public dashboard separates static UI deployment from volatile GitHub state.

## Data flow

1. GitHub Pages loads `docs/dashboard/dashboard.json` as a validated public-only baseline.
2. The browser resolves the production live endpoint from `docs/dashboard/live-config.json` (or `/api/dashboard-live` when the UI itself is served by Vercel).
3. The live endpoint reads current public repositories, open Issue/PR state, latest workflow run per repository, and recent Issue/PR activity from GitHub REST.
4. The browser overlays only volatile `repositories`, `workItems`, and `activity`. Heavy monthly stats remain from the baseline snapshot.
5. If the live endpoint is missing, stale, rate-limited, or invalid, the browser keeps the baseline and displays `SNAPSHOT FALLBACK` or `STALE`; it never labels stale data as live.

## Baseline refresh and UI deployment

The baseline snapshot is a fallback and the source for heavy monthly statistics; it is not the normal freshness path for Issue/PR/workflow/activity state.

- `push` to relevant dashboard/docs paths rebuilds and deploys the static UI and baseline.
- `workflow_dispatch` performs an explicit full baseline refresh.
- The scheduled baseline refresh runs once per day at 09:17 Asia/Tokyo (`17 0 * * *` in UTC).
- Page open and tab return freshness come from the live endpoint and do not require a Pages rebuild.

Keeping the scheduled baseline away from the start of the UTC hour also avoids GitHub Actions' documented high-load period for scheduled workflows.

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

`docs/dashboard/live-config.json` contains the verified production HTTPS endpoint used by GitHub Pages. The static artifact contains only that public endpoint URL; the GitHub credential remains server-side.

Production verification must check both layers independently:

1. the live endpoint returns a valid public-only payload with acceptable `requestBudget` and freshness metadata,
2. the Pages dashboard loads its baseline, overlays the live response, and renders `LIVE`,
3. endpoint failure or stale data renders `SNAPSHOT FALLBACK` or `STALE` rather than claiming freshness.

If the production live endpoint changes, update `docs/dashboard/live-config.json` only after verifying the new endpoint and rerunning the production smoke test.
