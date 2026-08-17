import unittest
from urllib.parse import parse_qs, urlparse

from dashboard.collectors.public_links import (
    collect_repository_links,
    enrich_repository_public_links,
)


class PublicLinksCollectorTest(unittest.TestCase):
    def test_configured_links_work_without_provider_tokens(self):
        config = {
            "repositoryLinks": [
                {
                    "owner": "KAFKA2306",
                    "name": "app",
                    "url": "https://app.pages.dev/",
                    "provider": "cloudflare",
                }
            ],
            "vercel": {"teamId": "team_test", "maxProjects": 100},
        }
        links, status = collect_repository_links(config)
        self.assertEqual(status["configured"], 1)
        self.assertEqual(status["vercel"]["status"], "unavailable")
        self.assertEqual(status["cloudflare"]["status"], "unavailable")
        self.assertEqual(links[0]["url"], "https://app.pages.dev")

    def test_live_provider_data_overrides_fallback_and_maps_by_github_repository(self):
        config = {
            "repositoryLinks": [
                {
                    "owner": "KAFKA2306",
                    "name": "app",
                    "url": "https://old-app.vercel.app",
                    "provider": "vercel",
                }
            ],
            "vercel": {"teamId": "team_test", "maxProjects": 100},
        }

        def fake_request(url, token):
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            if parsed.netloc == "api.vercel.com" and parsed.path == "/v9/projects":
                return {"projects": [{"id": "p_app", "name": "app"}]}
            if parsed.netloc == "api.vercel.com" and parsed.path == "/v6/deployments":
                self.assertEqual(query["limit"], ["20"])
                return {
                    "deployments": [
                        {"state": "ERROR"},
                        {
                            "state": "READY",
                            "meta": {
                                "githubCommitOrg": "KAFKA2306",
                                "githubCommitRepo": "app",
                            },
                        },
                    ]
                }
            if parsed.netloc == "api.vercel.com" and parsed.path.endswith("/p_app/domains"):
                return {
                    "domains": [
                        {
                            "name": "app-kafka2306s-projects.vercel.app",
                            "verified": True,
                        },
                        {"name": "app.vercel.app", "verified": True},
                    ]
                }
            if parsed.netloc == "api.cloudflare.com":
                return {
                    "result": [
                        {
                            "subdomain": "app.pages.dev",
                            "source": {
                                "type": "github",
                                "config": {
                                    "owner": "KAFKA2306",
                                    "repo_name": "app",
                                },
                            },
                        },
                        {
                            "subdomain": "direct-upload.pages.dev",
                            "source": {"type": "direct_upload"},
                        },
                    ]
                }
            raise AssertionError(url)

        links, status = collect_repository_links(
            config,
            vercel_token="vercel-token",
            cloudflare_account_id="account",
            cloudflare_token="cloudflare-token",
            request_fn=fake_request,
        )
        by_provider = {link["provider"]: link for link in links}
        self.assertEqual(by_provider["vercel"]["url"], "https://app.vercel.app")
        self.assertEqual(by_provider["cloudflare"]["url"], "https://app.pages.dev")
        self.assertEqual(status["vercel"]["mapped"], 1)
        self.assertEqual(status["cloudflare"]["mapped"], 1)

        repositories = [
            {
                "owner": "KAFKA2306",
                "name": "app",
                "publicLinks": [
                    {
                        "kind": "pages",
                        "url": "https://kafka2306.github.io/app/",
                    }
                ],
            }
        ]
        enrich_repository_public_links(repositories, links)
        self.assertEqual(
            {link["url"].rstrip("/") for link in repositories[0]["publicLinks"]},
            {
                "https://kafka2306.github.io/app",
                "https://app.vercel.app",
                "https://app.pages.dev",
            },
        )


if __name__ == "__main__":
    unittest.main()
