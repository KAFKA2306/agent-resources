from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen

TRENDING_URL = "https://github.com/trending?since={window}"
REPO_RE = re.compile(r'<h2[^>]*class="[^"]*h3[^"]*lh-condensed[^"]*"[^>]*>.*?<a[^>]+href="/([^"?#]+/[^"?#]+)"', re.S)

@dataclass(frozen=True)
class BenchmarkEntry:
    observed_at: str
    ranking_authority: str
    ranking_window: str
    rank: int
    repository: str
    benchmark_revision: str | None = None
    stars_delta: int | None = None
    activity_evidence: str = "UNVERIFIED"
    capability: str = "UNVERIFIED"
    local_status: str = "UNVERIFIED"
    decision: str = "PENDING_REVIEW"
    reason: str = "ranked_by_github_trending"
    adopted_revision: str | None = None
    last_evaluated_revision: str | None = None


def parse_trending(html: str, *, window: str, observed_at: str) -> list[BenchmarkEntry]:
    repos: list[str] = []
    for match in REPO_RE.finditer(html):
        repo = unescape(match.group(1)).strip("/")
        if repo.count("/") != 1 or repo in repos:
            continue
        repos.append(repo)
    return [BenchmarkEntry(observed_at, "github-trending", window, i, repo) for i, repo in enumerate(repos, 1)]


def fetch_window(window: str) -> list[BenchmarkEntry]:
    req = Request(TRENDING_URL.format(window=window), headers={"User-Agent": "agent-resources-factory-benchmark/1"})
    with urlopen(req, timeout=20) as response:
        html = response.read().decode("utf-8", errors="replace")
    observed = datetime.now(timezone.utc).isoformat()
    entries = parse_trending(html, window=window, observed_at=observed)
    if not entries:
        raise RuntimeError(f"GitHub Trending returned no parseable repositories for {window}")
    return entries


def merge_ledger(path: Path, incoming: list[BenchmarkEntry]) -> dict[str, object]:
    existing: dict[str, object] = {"schema_version": 1, "entries": []}
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
    rows = list(existing.get("entries", []))
    keys = {(r.get("repository"), r.get("ranking_window"), r.get("benchmark_revision"), r.get("observed_at", "")[:10]) for r in rows if isinstance(r, dict)}
    for entry in incoming:
        row = asdict(entry)
        key = (row["repository"], row["ranking_window"], row["benchmark_revision"], row["observed_at"][:10])
        if key not in keys:
            rows.append(row); keys.add(key)
    return {"schema_version": 1, "entries": rows[-1000:]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default="dashboard/oss-benchmark-ledger.json")
    parser.add_argument("--windows", nargs="+", default=["daily", "monthly"], choices=["daily", "weekly", "monthly"])
    args = parser.parse_args()
    entries: list[BenchmarkEntry] = []
    failures: list[str] = []
    for window in args.windows:
        try:
            entries.extend(fetch_window(window))
        except Exception as exc:
            failures.append(f"{window}:{type(exc).__name__}:{exc}")
    if not entries:
        print(json.dumps({"status": "UNVERIFIED", "failures": failures})); return 2
    path = Path(args.ledger)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merge_ledger(path, entries), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS" if not failures else "PARTIAL", "entries": len(entries), "failures": failures}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
