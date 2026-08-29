import json
import unittest
from pathlib import Path

from dashboard.collectors.github_api import GitHubApiError, fetch_paginated
from dashboard.collectors.repositories import collect_repositories, infer_public_links

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
        self.assertTrue(all("group" not in repo for repo in repositories))

    def test_topics_do_not_create_repository_classification(self):
        repositories = collect_repositories(self.config, fetcher=lambda url, token=None: self.raw)
        self.assertTrue(all("group" not in repo for repo in repositories))

    def test_public_links_include_homepage_and_github_pages(self):
        links = infer_public_links(
            {"homepage": "https://example.com/app", "has_pages": True},
            "KAFKA2306",
            "vrmine",
        )
        self.assertEqual(
            links,
            [
                {"kind": "front", "url": "https://example.com/app"},
                {"kind": "pages", "url": "https://kafka2306.github.io/vrmine/"},
            ],
        )

    def test_public_links_deduplicate_homepage_that_matches_pages(self):
        links = infer_public_links(
            {"homepage": "https://kafka2306.github.io/vrmine/", "has_pages": True},
            "KAFKA2306",
            "vrmine",
        )
        self.assertEqual(
            links,
            [{"kind": "front", "url": "https://kafka2306.github.io/vrmine/"}],
        )

    def test_public_links_ignore_non_https_homepage(self):
        links = infer_public_links(
            {"homepage": "http://example.com/app", "has_pages": False},
            "KAFKA2306",
            "vrmine",
        )
        self.assertEqual(links, [])

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
