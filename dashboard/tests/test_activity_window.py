import unittest
from dashboard.build import build_snapshot


class ActivityWindowTest(unittest.TestCase):
    def setUp(self):
        self.public_repo = {"id": "R_public", "owner": "example-owner", "name": "public", "url": "https://github.com/example-owner/public", "group": "core", "visibility": "public", "updatedAt": "2026-08-13T10:00:00Z"}
        self.private_repo = dict(self.public_repo, id="R_private", name="private", url="https://github.com/example-owner/private", visibility="private")

    def test_old_open_work_item_does_not_leak_into_recent_activity(self):
        stale_open = {"id": "R_public:issue:1", "repositoryId": "R_public", "kind": "issue", "number": 1, "title": "old open issue", "url": "https://github.com/example-owner/public/issues/1", "state": "open", "updatedAt": "2026-08-01T00:00:00Z"}
        snapshot = build_snapshot([self.public_repo], [stale_open], [], generated_at="2026-08-13T12:00:00Z")
        self.assertEqual(len(snapshot["workItems"]), 1)
        self.assertEqual(snapshot["activity"], [])

    def test_recent_activity_keeps_public_and_drops_private(self):
        activity = [
            {"id": "activity:R_public:pull_request:8", "repositoryId": "R_public", "kind": "pull_request", "occurredAt": "2026-08-10T09:00:00Z", "url": "https://github.com/example-owner/public/pull/8", "summary": "merged change"},
            {"id": "activity:R_private:issue:9", "repositoryId": "R_private", "kind": "issue", "occurredAt": "2026-08-12T09:00:00Z", "url": "https://github.com/example-owner/private/issues/9", "summary": "must not leak"},
        ]
        snapshot = build_snapshot([self.public_repo, self.private_repo], [], [], activity_items=activity, generated_at="2026-08-13T12:00:00Z")
        self.assertEqual([item["summary"] for item in snapshot["activity"]], ["merged change"])


if __name__ == "__main__":
    unittest.main()
