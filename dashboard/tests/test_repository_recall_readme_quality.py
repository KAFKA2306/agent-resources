import unittest

from dashboard.repository_recall import UNKNOWN_MATCH, UNKNOWN_PURPOSE, merge_index


class RepositoryRecallReadmeQualityTests(unittest.TestCase):
    def repo(self, name):
        return {
            "id": f"R_{name}",
            "owner": "KAFKA2306",
            "name": name,
            "url": f"https://github.com/KAFKA2306/{name}",
            "visibility": "public",
            "archived": False,
            "updatedAt": "2026-08-18T00:00:00Z",
            "group": "unclassified",
            "publicLinks": [],
        }

    def facts(self, name, readme_text, fingerprint="a" * 64):
        return {
            "name": name,
            "url": f"https://github.com/KAFKA2306/{name}",
            "sources": [
                {
                    "kind": "repository",
                    "url": f"https://github.com/KAFKA2306/{name}",
                    "status": "ok",
                    "fingerprint": "metadata-sha",
                },
                {
                    "kind": "readme",
                    "url": f"https://github.com/KAFKA2306/{name}/blob/main/README.md",
                    "status": "ok",
                    "fingerprint": "readme-sha",
                },
            ],
            "sourceFingerprint": fingerprint,
            "description": None,
            "topics": [],
            "readmeText": readme_text,
        }

    def entry(self, name, purpose, fingerprint="a" * 64):
        return {
            "name": name,
            "purpose": purpose,
            "matches": [purpose],
            "notFor": [],
            "url": f"https://github.com/KAFKA2306/{name}",
            "sources": self.facts(name, "", fingerprint)["sources"],
            "sourceFingerprint": fingerprint,
            "checkedAt": "2026-08-18T00:00:00Z",
            "needsReview": False,
        }

    def merge(self, name, readme, existing=None):
        return merge_index(
            [self.repo(name)],
            {name: self.facts(name, readme)},
            existing=existing or {"repositories": []},
            now="2026-08-18T03:00:00Z",
        )["repositories"][0]

    def test_prefers_project_description_over_generic_problem_statement(self):
        entry = self.merge(
            "books",
            """# books

本が増えるほど、「持っているか」「読んだか」「どの版か」が一つの答えではなくなる。

books は蔵書・読書状態・版情報を保存し、検索・比較できるようにする個人書籍管理ツールです。
""",
        )
        self.assertFalse(entry["needsReview"])
        self.assertIn("個人書籍管理ツール", entry["purpose"])
        self.assertNotEqual(
            entry["purpose"],
            "本が増えるほど、「持っているか」「読んだか」「どの版か」が一つの答えではなくなる。",
        )

    def test_rejects_public_page_url_as_repository_purpose(self):
        entry = self.merge(
            "DominionDeckDrawSimlator",
            """# DominionDeckDrawSimlator

公開ページ: https://kafka2306.github.io/DominionDeckDrawSimlator/
""",
        )
        self.assertTrue(entry["needsReview"])
        self.assertEqual(entry["purpose"], UNKNOWN_PURPOSE)
        self.assertEqual(entry["matches"], [UNKNOWN_MATCH])

    def test_rejects_stackblitz_edit_prompt(self):
        entry = self.merge(
            "VRChat-bolt",
            """# VRChat-bolt

Edit in StackBlitz next generation editor ⚡️
""",
        )
        self.assertTrue(entry["needsReview"])
        self.assertEqual(entry["purpose"], UNKNOWN_PURPOSE)

    def test_skips_contract_heading_for_actual_application_description(self):
        entry = self.merge(
            "VeilVoice",
            """# FINAL ZERO-TRUST DELIVERY CONTRACT

VeilVoice is a local voice conversion application that records microphone audio and converts it for private real-time communication.
""",
        )
        self.assertFalse(entry["needsReview"])
        self.assertTrue(entry["purpose"].startswith("VeilVoice is a local voice conversion application"))

    def test_skips_documentation_index_for_actual_system_description(self):
        entry = self.merge(
            "yt4",
            """# yt4 Documentation Index

yt4 is an auditable media generation system that creates video assets and records publication evidence.
""",
        )
        self.assertFalse(entry["needsReview"])
        self.assertIn("media generation system", entry["purpose"])

    def test_re_evaluates_previous_auto_semantic_when_extractor_is_stricter(self):
        name = "VRChat-bolt"
        old = self.entry(name, "Edit in StackBlitz next generation editor ⚡️")
        entry = self.merge(
            name,
            """# VRChat-bolt

Edit in StackBlitz next generation editor ⚡️
""",
            existing={"repositories": [old]},
        )
        self.assertTrue(entry["needsReview"])
        self.assertEqual(entry["purpose"], UNKNOWN_PURPOSE)
        self.assertIsNone(entry["checkedAt"])


if __name__ == "__main__":
    unittest.main()
