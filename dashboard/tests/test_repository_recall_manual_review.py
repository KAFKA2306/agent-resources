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
    "nonfarmpayroll",
    "prompt-vault",
    "readable-github",
    "rule-scribe-games",
    "skew",
    "vmatch2",
    "vrc-pilot-test",
    "vrcgimmicknetwork",
    "VRChat-bolt",
    "vrcviewer",
    "VRPhotoJourney",
    "Year2035",
    "yt4",
}

NO_EVIDENCE = {"multiomics", "robot", "space"}


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

    def test_all_evidence_backed_remaining_repositories_are_reviewed(self):
        self.assertTrue(REVIEWED.issubset(self.overrides))

    def test_empty_repositories_are_not_promoted_without_evidence(self):
        self.assertTrue(NO_EVIDENCE.isdisjoint(self.overrides))

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
