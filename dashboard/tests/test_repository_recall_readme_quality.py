import base64
import unittest

from dashboard.repository_recall import (
    UNKNOWN_MATCH,
    UNKNOWN_PURPOSE,
    collect_source_fact,
    merge_index,
)


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

    def merge(self, name, readme):
        return merge_index(
            [self.repo(name)],
            {name: self.facts(name, readme)},
            existing={"repositories": []},
            now="2026-08-18T03:00:00Z",
        )["repositories"][0]

    def assert_unreviewed(self, entry):
        self.assertTrue(entry["needsReview"])
        self.assertEqual(entry["purpose"], UNKNOWN_PURPOSE)
        self.assertEqual(entry["matches"], [UNKNOWN_MATCH])

    def test_collect_source_fact_decodes_existing_readme_api_content(self):
        repo = self.repo("articles")
        readme_text = "# articles\n\n技術記事を作るrepositoryです。"

        def request_fn(url, token):
            if url.endswith("/readme"):
                return (
                    {
                        "sha": "readme-sha",
                        "html_url": "https://github.com/KAFKA2306/articles/blob/main/README.md",
                        "encoding": "base64",
                        "content": base64.b64encode(readme_text.encode("utf-8")).decode("ascii"),
                    },
                    {},
                )
            return (
                {
                    "private": False,
                    "visibility": "public",
                    "archived": False,
                    "description": "articles",
                    "topics": [],
                    "default_branch": "main",
                },
                {},
            )

        result = collect_source_fact(repo, request_fn=request_fn)
        self.assertEqual(result["readmeText"], readme_text)
        self.assertNotIn("readmeText", result["sources"][1])

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

    def test_accepts_purpose_paragraph_in_overview_section(self):
        entry = self.merge(
            "articles",
            """# articles

## 概要

articles は実測や失敗を根拠に、読後の判断を改善する技術記事を作成・管理するrepositoryです。

## Usage

記事を公開します。
""",
        )
        self.assertFalse(entry["needsReview"])
        self.assertIn("技術記事を作成・管理するrepository", entry["purpose"])

    def test_rejects_public_page_url_as_repository_purpose(self):
        entry = self.merge(
            "DominionDeckDrawSimlator",
            """# DominionDeckDrawSimlator

公開ページ: https://kafka2306.github.io/DominionDeckDrawSimlator/
""",
        )
        self.assert_unreviewed(entry)

    def test_rejects_stackblitz_edit_prompt(self):
        entry = self.merge(
            "VRChat-bolt",
            """# VRChat-bolt

Edit in StackBlitz next generation editor ⚡️
""",
        )
        self.assert_unreviewed(entry)

    def test_rejects_dependency_detail_outside_purpose_section(self):
        entry = self.merge(
            "dancer",
            """# dancer

## Setup

依存管理と実行は uv を正とし、Blender Pythonの bpy==4.2.0 と numpy を導入します。
""",
        )
        self.assert_unreviewed(entry)

    def test_rejects_runtime_version_detail_outside_purpose_section(self):
        entry = self.merge(
            "AutoPhotogrammetry",
            """# AutoPhotogrammetry

## Runtime backend

本repositoryではCUDA 11.8とPyTorch 2.1を固定したruntime imageを利用します。
""",
        )
        self.assert_unreviewed(entry)

    def test_rejects_license_paragraph_as_purpose(self):
        entry = self.merge(
            "readable-github",
            """# readable-github

## License

このプロジェクトはMITライセンスです。自由に利用、改変、配布できます。
""",
        )
        self.assert_unreviewed(entry)

    def test_rejects_standard_library_requirement_as_purpose(self):
        entry = self.merge(
            "vrcviewer",
            """# vrcviewer

## Requirements

Python標準ライブラリだけで実行できます。外部packageは不要です。
""",
        )
        self.assert_unreviewed(entry)

    def test_skips_contract_heading_for_actual_application_description(self):
        entry = self.merge(
            "VeilVoice",
            """# FINAL ZERO-TRUST DELIVERY CONTRACT

## Overview

VeilVoice is a local voice conversion application that records microphone audio and converts it for private real-time communication.
""",
        )
        self.assertFalse(entry["needsReview"])
        self.assertTrue(entry["purpose"].startswith("VeilVoice is a local voice conversion application"))

    def test_skips_documentation_index_for_actual_system_description(self):
        entry = self.merge(
            "yt4",
            """# yt4 Documentation Index

## Overview

yt4 is an auditable media generation system that creates video assets and records publication evidence.
""",
        )
        self.assertFalse(entry["needsReview"])
        self.assertIn("media generation system", entry["purpose"])

    def test_rejects_paths_and_operational_details_as_purpose(self):
        entry = self.merge(
            "prompt-vault",
            """# prompt-vault

## Publishing

本projectでは src/prompts/ を編集し、dist/prompts/index.json と docs/prompts.md を生成して公開します。
""",
        )
        self.assert_unreviewed(entry)


if __name__ == "__main__":
    unittest.main()
