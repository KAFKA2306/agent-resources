from dashboard.factory_state import build_factory_state


def _verified_signal(index: int, duration_minutes: int) -> dict[str, object]:
    return {
        "id": f"work-{index}",
        "conclusion": "success",
        "merged": True,
        "deployed": True,
        "probed": True,
        "started_at": "2026-09-26T00:00:00Z",
        "updated_at": f"2026-09-26T00:{duration_minutes:02d}:00Z",
    }


def test_lead_time_percentiles_use_verified_worklines_only() -> None:
    signals = [_verified_signal(i, minutes) for i, minutes in enumerate((1, 2, 3, 4, 5), 1)]
    signals.append(
        {
            "id": "still-active",
            "started_at": "2026-09-26T00:00:00Z",
            "updated_at": "2026-09-26T00:59:00Z",
        }
    )

    state = build_factory_state(
        signals,
        main_sha="abc123",
        generated_at="2026-09-26T01:00:00Z",
    )

    assert state["metrics"]["leadTimeP50Seconds"] == 180.0
    assert state["metrics"]["leadTimeP95Seconds"] == 300.0


def test_lead_time_percentiles_are_unknown_without_verified_timing_evidence() -> None:
    state = build_factory_state(
        [{"id": "active"}],
        main_sha="abc123",
        generated_at="2026-09-26T01:00:00Z",
    )

    assert state["metrics"]["leadTimeP50Seconds"] is None
    assert state["metrics"]["leadTimeP95Seconds"] is None
