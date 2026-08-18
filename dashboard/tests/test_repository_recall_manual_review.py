import json
import unittest
from pathlib import Path

from dashboard.repository_recall import search_index


ROOT = Path(__file__).resolve().parents[1]
OVERRIDES_PATH = ROOT / "config" / "repository-recall-overrides.json"

REVIEWED = {
    "AutoPhotogrammetry",
    "boardgamelist",
    "bodogenomikata2",
    "ComfyUI-KLingAI-API",
    "DominionDeckDrawSimlator",
    "furuyoni",
    "kafka",
    "KAFKA2306",
    "marvelousdesigner",
    "multiomics",
    "nonfarmpayroll",
    "prompt-vault",
    "readable-github",
    "robot",
    "rule-scribe-games",
    "skew",
    "space",
    "vmatch2",
    "vrc-pilot-test",
    "vrcgimmicknetwork",
    "VRChat-bolt",
    "vrcviewer",
    "VRPhotoJourney",
    "Year2035",
    "yt4",
}


class RepositoryRecallManualReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overrides = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))

    def document(self, names):
        repositories = []
        for name in names:
            semantic = self.overrides[name]
            repositories.append(
                {
                    "name": name,
                    "purpose": semantic["purpose"],
                    "matches": semantic["matches"],
                    "notFor": semantic["notFor"],
                    "url": f"https://github.com/KAFKA2306/{name}",
                    "sources": [
                        {
                            "kind": "repository",
                            "url": f"https://github.com/KAFKA2306/{name}",
                            "status": "ok",
                            "fingerprint": "metadata-sha",
                        }
                    ],
                    "sourceFingerprint": "a" * 64,
                    "checkedAt": "2026-08-18T00:00:00Z",
                    "needsReview": False,
                }
            )
        return {"repositories": repositories}

    def test_all_manually_audited_repositories_have_reviewed_semantics(self):
        self.assertTrue(REVIEWED.issubset(self.overrides))

    def test_multiomics_is_explicitly_planned_not_falsely_implemented(self):
        semantic = self.overrides["multiomics"]
        self.assertIn("正準ターゲット", semantic["purpose"])
        self.assertIn("未materialized", semantic["purpose"])
        result = search_index(
            "Multiomicsの正準repository",
            self.document({"multiomics"}),
        )
        self.assertEqual(result["selected"], "multiomics")

    def test_non_canonical_empty_repositories_are_not_selected(self):
        cases = [
            ("robot", "robot"),
            ("robot", "robotics"),
            ("robot", "ロボット"),
            ("space", "space"),
            ("space", "reusable rockets"),
            ("space", "ロケット"),
        ]
        for name, query in cases:
            with self.subTest(name=name, query=query):
                result = search_index(query, self.document({name}))
                self.assertIsNone(result["selected"])

    def test_nearby_repository_queries_stay_distinct(self):
        cases = [
            (
                {"AutoPhotogrammetry", "VRPhotoJourney"},
                "動画からGaussian Splat PLYを作る",
                "AutoPhotogrammetry",
            ),
            (
                {"AutoPhotogrammetry", "VRPhotoJourney"},
                "Unityで写真slideshowを作る",
                "VRPhotoJourney",
            ),
            (
                {"VRChat-bolt", "vrcviewer"},
                "VRChatワールド発見UIのprototype",
                "VRChat-bolt",
            ),
            (
                {"VRChat-bolt", "vrcviewer"},
                "CSVからVRChat gallery HTMLを生成",
                "vrcviewer",
            ),
            (
                {"boardgamelist", "bodogenomikata2", "rule-scribe-games"},
                "ボードゲームのルールを版ごとに出典付きで調べる",
                "boardgamelist",
            ),
            (
                {"boardgamelist", "bodogenomikata2", "rule-scribe-games"},
                "ボードゲームのルールを素早く質問して出典へ戻る",
                "bodogenomikata2",
            ),
            (
                {"boardgamelist", "bodogenomikata2", "rule-scribe-games"},
                "RuleScribe Gamesでボードゲームルールを検索",
                "rule-scribe-games",
            ),
            (
                {"kafka", "KAFKA2306"},
                "KAFKAの個人サイトを見る",
                "kafka",
            ),
            (
                {"kafka", "KAFKA2306"},
                "KAFKA2306の主要プロジェクト一覧を見る",
                "KAFKA2306",
            ),
        ]
        for names, query, expected in cases:
            with self.subTest(query=query):
                result = search_index(query, self.document(names))
                self.assertEqual(result["selected"], expected)


if __name__ == "__main__":
    unittest.main()
