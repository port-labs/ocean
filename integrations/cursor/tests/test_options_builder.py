from core.options_builder import build_admin_options, build_analytics_options


def test_build_analytics_options() -> None:
    result = build_analytics_options("30d", "0d")
    assert result["startDate"] == "30d"
    assert result["endDate"] == "0d"
    assert result["page"] == 1
    assert result["pageSize"] == 500


def test_build_admin_options_converts_to_epoch_ms() -> None:
    result = build_admin_options("30d", "0d")
    assert result["startDate"] < result["endDate"]
    assert result["page"] == 1
    assert result["pageSize"] == 500


def test_build_admin_options_window_does_not_exceed_30_days() -> None:
    result = build_admin_options("30d", "0d")
    span_days = (result["endDate"] - result["startDate"]) / (1000 * 60 * 60 * 24)
    assert span_days <= 30
