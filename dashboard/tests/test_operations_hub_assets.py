from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_JS = ROOT / "docs" / "dashboard" / "dashboard.js"
DASHBOARD_CSS = ROOT / "docs" / "dashboard" / "dashboard.css"


def test_gate_detail_exposes_existing_work_item_evidence() -> None:
    source = DASHBOARD_JS.read_text(encoding="utf-8")

    assert "item.laneReason" in source
    assert "item.updatedAt" in source
    assert 'link.href = item.url' in source
    assert 'row.className = "gate-item"' in source
    assert 'meta.className = "gate-item-meta"' in source
    assert 'reason.className = "gate-item-reason"' in source


def test_gate_evidence_cards_have_scannable_styles() -> None:
    source = DASHBOARD_CSS.read_text(encoding="utf-8")

    for selector in (".gate-item{", ".gate-item-meta{", ".gate-item-reason{"):
        assert selector in source
