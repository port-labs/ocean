from core.options_builder import (
    build_admin_options,
    build_analytics_options,
    build_team_skill_usage_options,
)


def test_build_analytics_options() -> None:
    result = build_analytics_options("30d", "0d")
    assert result["startDate"] == "30d"
    assert result["endDate"] == "0d"
    assert set(result.keys()) == {"startDate", "endDate"}


def test_build_team_skill_usage_options_omits_users_when_unset() -> None:
    result = build_team_skill_usage_options("30d", "0d")
    assert result == {"startDate": "30d", "endDate": "0d"}


def test_build_team_skill_usage_options_passes_users_filter() -> None:
    result = build_team_skill_usage_options(
        "14d", "0d", users="alice@example.com,user_abc123"
    )
    assert result == {
        "startDate": "14d",
        "endDate": "0d",
        "users": "alice@example.com,user_abc123",
    }


def test_build_admin_options_converts_to_epoch_ms() -> None:
    result = build_admin_options("30d", "0d")
    assert result["startDate"] < result["endDate"]
    assert set(result.keys()) == {"startDate", "endDate"}


def test_build_admin_options_window_does_not_exceed_30_days() -> None:
    result = build_admin_options("30d", "0d")
    span_days = (result["endDate"] - result["startDate"]) / (1000 * 60 * 60 * 24)
    assert span_days <= 30
