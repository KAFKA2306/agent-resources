import unittest

from dashboard_snapshot_production_e2e import _same_timestamp
from production_resource_health import verify_http_resources


class ProductionResourceHealthTests(unittest.TestCase):
    def test_timestamp_provenance_compares_instants_not_localized_display_text(self):
        self.assertTrue(
            _same_timestamp("2026-11-28T15:24:45.592Z", "2026-11-28T15:24:45.592+00:00")
        )
        self.assertTrue(
            _same_timestamp("2026-11-28T15:24:45.592871Z", "2026-11-28T15:24:45.592Z")
        )
        self.assertFalse(
            _same_timestamp("2026-11-28T15:24:46.000Z", "2026-11-28T15:24:45.592Z")
        )
        self.assertFalse(_same_timestamp("2026-11-28T15:24:45.592", "2026-11-28T15:24:45.592Z"))

    def test_checks_the_production_pages_static_resources(self):
        requests = []

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        def open_url(request, timeout):
            requests.append((request.full_url, timeout))
            return Response()

        results = verify_http_resources(
            "https://agent-resources-one.vercel.app/dashboard/",
            "abc123",
            open_url=open_url,
        )

        self.assertEqual(len(results), 7)
        self.assertTrue(all(status == 200 for _, status in results))
        self.assertEqual(len(requests), 7)
        self.assertIn(
            "https://agent-resources-one.vercel.app/dashboard/factory-state.json?v=abc123",
            [url for url, _ in requests],
        )

    def test_non_200_snapshot_response_fails_closed(self):
        class Response:
            status = 502

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        with self.assertRaisesRegex(ValueError, "production root returned HTTP 502"):
            verify_http_resources(
                "https://agent-resources-one.vercel.app/dashboard/",
                "abc123",
                open_url=lambda *_args, **_kwargs: Response(),
            )


if __name__ == "__main__":
    unittest.main()
