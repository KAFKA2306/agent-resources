import io
import json
import unittest
from http.client import RemoteDisconnected
from unittest.mock import call, patch
from urllib.error import HTTPError

from dashboard.collectors.github_api import GitHubApiError, request_json


class FakeResponse:
    def __init__(self, body, headers=None):
        self._body = body
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._body


class GitHubApiTransportRetryTest(unittest.TestCase):
    @patch("dashboard.collectors.github_api.time.sleep")
    @patch("dashboard.collectors.github_api.urlopen")
    def test_remote_disconnect_retries_then_succeeds(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = [
            RemoteDisconnected("remote closed"),
            FakeResponse(json.dumps({"ok": True}).encode("utf-8"), {"X-Test": "yes"}),
        ]

        payload, headers = request_json("https://api.github.com/test")

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(headers["X-Test"], "yes")
        self.assertEqual(mock_urlopen.call_count, 2)
        mock_sleep.assert_called_once_with(0.5)

    @patch("dashboard.collectors.github_api.time.sleep")
    @patch("dashboard.collectors.github_api.urlopen")
    def test_remote_disconnect_exhaustion_fails_after_three_attempts(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = RemoteDisconnected("remote closed")

        with self.assertRaisesRegex(GitHubApiError, "after 3 transport attempts"):
            request_json("https://api.github.com/test")

        self.assertEqual(mock_urlopen.call_count, 3)
        self.assertEqual(mock_sleep.call_args_list, [call(0.5), call(1.5)])

    @patch("dashboard.collectors.github_api.time.sleep")
    @patch("dashboard.collectors.github_api.urlopen")
    def test_http_error_is_not_transport_retried(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = HTTPError(
            "https://api.github.com/test",
            503,
            "Service Unavailable",
            {},
            io.BytesIO(b'{"message":"unavailable"}'),
        )

        with self.assertRaises(GitHubApiError) as context:
            request_json("https://api.github.com/test")

        self.assertEqual(context.exception.status, 503)
        self.assertEqual(mock_urlopen.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("dashboard.collectors.github_api.time.sleep")
    @patch("dashboard.collectors.github_api.urlopen")
    def test_invalid_json_fails_closed_without_retry(self, mock_urlopen, mock_sleep):
        mock_urlopen.return_value = FakeResponse(b"not-json")

        with self.assertRaisesRegex(GitHubApiError, "returned invalid JSON"):
            request_json("https://api.github.com/test")

        self.assertEqual(mock_urlopen.call_count, 1)
        mock_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
