import json
import unittest
from pathlib import Path

from dashboard.collectors.github_api import GitHubApiError, fetch_paginated
from dashboard.collectors.repositories import collect_repositories, infer_group

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FIXTURE = ROOT / "fixtures" / "repositories.config.example.json"
API_FIXTURE = ROOT / "fixtures" / "repositories.api.example.json"


class RepositoryCollectorTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(CONFIG_FIXTURE.read_text(encoding="utf-8"))
        self.raw = json.loads(API_FIXTURE.read_text(encoding="utf-8"))

    def test_all_public_active_repositories_are_emitted(self):
        def fetcher(url, token=None):
            self.assertIn("/users/example-owner/repos", url)
            return self.raw

        repositories = collect_repositories(self.config, fetcher=fetcher)
        self.assertEqual(
            [repo["name"] for repo in repositories],
            ["public-active", "public-language"],
        )
        self.assertTrue(all(repo["visibility"] == "public" for repo in repositories))
        self.assertTrue(all(repo["archived"] is False for repo in repositories))

    def test_project_zone_is_derived_only_from_explicit_agent_zone_topic(self):
        repositories = collect_repositories(self.config, fetcher=lambda url, token=None: self.raw)
        by_name = {repo["name"]: repo for repo in repositories}
        self.assertEqual(by_name["public-active"]["group"], "core")
        self.assertEqual(by_name["public-language"]["group"], "unclassified")

    def test_programming_language_never_becomes_a_project_zone(self):
        self.assertEqual(
            infer_group({"topics": [], "language": "Python"}),
            "unclassified",
        )
        self.assertEqual(
            infer_group({"topics": [], "language": "JavaScript"}),
            "unclassified",
        )

    def test_agent_zone_topic_wins_without_language_inference(self):
        self.assertEqual(
            infer_group(
                {
                    "topics": ["agent-zone-investing", "python"],
                    "language": "Python",
                }
            ),
            "investing",
        )

    def test_all_unclassified_repositories_share_one_fallback(self):
        groups = {
            infer_group({"topics": [], "language": "Python"}),
            infer_group({"topics": [], "language": "TypeScript"}),
            infer_group({"topics": [], "language": None}),
        }
        self.assertEqual(groups, {"unclassified"})

    def test_private_repository_is_rejected(self):
        def fetcher(url, token=None):
            return [self.raw[1]]

        self.assertEqual(collect_repositories(self.config, fetcher=fetcher), [])

    def test_archived_repository_is_always_rejected(self):
        def fetcher(url, token=None):
            return [self.raw[2]]

        self.assertEqual(collect_repositories(self.config, fetcher=fetcher), [])

    def test_pagination_failure_does_not_return_partial_data(self):
        calls = []

        def request_fn(url, token=None):
            calls.append(url)
            if url.endswith("page=2"):
                raise GitHubApiError("simulated page failure")
            return [self.raw[0]], {
                "Link": '<https://api.github.com/users/example-owner/repos?page=2>; rel="next"'
            }

        with self.assertRaises(GitHubApiError):
            fetch_paginated(
                "https://api.github.com/users/example-owner/repos?page=1",
                request_fn=request_fn,
            )
        self.assertEqual(len(calls), 2)

    def test_all_pages_are_collected_before_normalization(self):
        def request_fn(url, token=None):
            if url.endswith("page=1"):
                return [self.raw[0]], {
                    "Link": '<https://api.github.com/users/example-owner/repos?page=2>; rel="next"'
                }
            return [self.raw[3]], {}

        pages = fetch_paginated(
            "https://api.github.com/users/example-owner/repos?page=1",
            request_fn=request_fn,
        )
        self.assertEqual(len(pages), 2)


if __name__ == "__main__":
    unittest.main()
