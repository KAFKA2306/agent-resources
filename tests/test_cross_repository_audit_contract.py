from pathlib import Path

AGENTS = Path(__file__).resolve().parents[1] / "AGENTS.md"


def test_cross_repository_issue_references_use_real_github_identity() -> None:
    text = AGENTS.read_text(encoding="utf-8")
    assert "owner/repo#number" in text
    assert "未起票候補へログ内通し番号や擬似Issue番号を付けない" in text


def test_cross_repository_claim_verification_is_not_aggregate() -> None:
    text = AGENTS.read_text(encoding="utf-8")
    for status in ("VERIFIED", "OBSERVED", "INFERRED", "UNVERIFIED"):
        assert status in text
    assert "複数claimを含むhandoff全体へ一括で `VERIFIED` を付けない" in text
