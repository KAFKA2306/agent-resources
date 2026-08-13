import unittest
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from dashboard.collectors.public_links import collect_public_links


class PublicLinksCollectorTest(unittest.TestCase):
    def setUp(self):
        self.config = {
            "profiles": [
                {"id": "github", "label": "GitHub", "url": "https://github.com/KAFKA2306", "category": "profile"},
                {"id": "zenn", "label": "Zenn", "url": "https://zenn.dev/kafka2306", "category": "writing"},
            ],
            "vercel": {"teamId": "team_test", "maxProjects": 100},
        }
        self.now = datetime(2026, 8, 13, 22, 0, tzinfo=timezone.utc)

    def test_missing_vercel_token_is_fail_soft(self):
        payload = collect_public_links(self.config, token=None, now=self.now)
        self.assertEqual(payload["sourceStatus"]["vercel"]["status"], "unavailable")
        self.assertEqual({link["id"] for link in payload["links"]}, {"github", "zenn"})

    def test_only_ready_production_projects_are_exposed(self):
        def fake_request(url, token):
            self.assertEqual(token, "test-token")
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            if parsed.path == "/v9/projects":
                return {"projects": [{"id": "p_ready", "name": "ready-app"}, {"id": "p_error", "name": "error-app"}, {"id": "p_ready_2", "name": "reader"}]}
            if parsed.path == "/v6/deployments":
                project = query["projectId"][0]
                if project == "p_error":
                    return {"deployments": [{"state": "ERROR", "url": "error.vercel.app"}]}
                return {"deployments": [{"state": "READY", "url": f"{project}-hash.vercel.app"}]}
            if parsed.path.endswith("/p_ready/domains"):
                return {"domains": [{"name": "ready-app-kafka2306s-projects.vercel.app", "verified": True}, {"name": "ready-app.vercel.app", "verified": True}]}
            if parsed.path.endswith("/p_ready_2/domains"):
                return {"domains": [{"name": "reader-git-main-kafka2306s-projects.vercel.app", "verified": True}, {"name": "reader-three-sooty.vercel.app", "verified": True}]}
            raise AssertionError(url)

        payload = collect_public_links(self.config, token="test-token", now=self.now, request_fn=fake_request)
        vercel = [link for link in payload["links"] if link["provider"] == "vercel"]
        self.assertEqual({link["label"] for link in vercel}, {"ready-app", "reader"})
        self.assertEqual({link["url"] for link in vercel}, {"https://ready-app.vercel.app", "https://reader-three-sooty.vercel.app"})
        self.assertEqual(payload["sourceStatus"]["vercel"], {"status": "ok", "discovered": 3, "ready": 2, "failed": 0})

    def test_duplicate_urls_are_collapsed(self):
        config = dict(self.config)
        config["profiles"] = self.config["profiles"] + [{"id": "github-alt", "label": "GitHub duplicate", "url": "https://github.com/KAFKA2306/", "category": "profile"}]
        payload = collect_public_links(config, token=None, now=self.now)
        urls = [link["url"] for link in payload["links"]]
        self.assertEqual(urls.count("https://github.com/KAFKA2306"), 1)


if __name__ == "__main__":
    unittest.main()
