import json
import unittest
from pathlib import Path
from urllib.parse import urlparse

from dashboard.collectors.public_links import (
    collect_repository_links,
    enrich_repository_public_links,
    normalize_configured_link,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "dashboard" / "config" / "public-links.json"
POKER_REPOSITORY = ("KAFKA2306", "poker-raise-quiz")
POKER_PUBLIC_URL = "https://kafka2306.github.io/poker-raise-quiz/"


class PublicLinksContractTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.entries = self.config["repositoryLinks"]

    def test_configured_links_are_unique_absolute_https_and_normalizable(self):
        self.assertIsInstance(self.entries, list)
        self.assertGreater(len(self.entries), 0)
        identities = set()

        for raw in self.entries:
            normalized = normalize_configured_link(raw)
            self.assertEqual(normalized["kind"], "front")
            parsed = urlparse(normalized["url"])
            self.assertEqual(parsed.scheme, "https")
            self.assertTrue(parsed.netloc)

            identity = (
                normalized["repository"]["owner"].lower(),
                normalized["repository"]["name"].lower(),
                normalized["provider"].lower(),
            )
            self.assertNotIn(identity, identities, f"duplicate public link identity: {identity}")
            identities.add(identity)

    def test_every_configured_link_survives_repository_enrichment(self):
        links, status = collect_repository_links(self.config)
        self.assertEqual(status["configured"], len(self.entries))

        repositories = [
            {
                "id": f"repo-{index}",
                "owner": raw["owner"],
                "name": raw["name"],
            }
            for index, raw in enumerate(self.entries)
        ]
        enriched = enrich_repository_public_links(repositories, links)

        by_repository = {
            (repo["owner"].lower(), repo["name"].lower()): repo for repo in enriched
        }
        for raw in self.entries:
            key = (raw["owner"].lower(), raw["name"].lower())
            repository = by_repository[key]
            actual_urls = {
                item["url"].rstrip("/")
                for item in repository.get("publicLinks", [])
                if item.get("kind") == "front"
            }
            self.assertIn(raw["url"].rstrip("/"), actual_urls)

    def test_poker_raise_quiz_canonical_public_link_is_required(self):
        matching = [
            raw
            for raw in self.entries
            if (raw.get("owner"), raw.get("name")) == POKER_REPOSITORY
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["url"], POKER_PUBLIC_URL)
        self.assertEqual(matching[0]["provider"], "github-pages")


if __name__ == "__main__":
    unittest.main()
