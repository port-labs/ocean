import pytest

from integration import CursorRelativeDateSelector, CursorTeamSkillUsageSelector


def test_selector_defaults_are_valid() -> None:
    selector = CursorRelativeDateSelector(query="true")
    assert selector.start_date == "30d"
    assert selector.end_date == "0d"


def test_selector_accepts_custom_window() -> None:
    selector = CursorRelativeDateSelector(query="true", startDate="14d", endDate="7d")
    assert selector.start_date == "14d"
    assert selector.end_date == "7d"


def test_selector_rejects_ranges_over_30_days() -> None:
    with pytest.raises(ValueError):
        CursorRelativeDateSelector(query="true", startDate="31d", endDate="0d")


def test_selector_rejects_start_before_end() -> None:
    with pytest.raises(ValueError):
        CursorRelativeDateSelector(query="true", startDate="5d", endDate="10d")


def test_selector_rejects_non_relative_format() -> None:
    with pytest.raises(ValueError):
        CursorRelativeDateSelector(query="true", startDate="2026-01-01", endDate="0d")


def test_team_skill_usage_selector_accepts_optional_users_filter() -> None:
    selector = CursorTeamSkillUsageSelector(
        query="true",
        users="alice@example.com,user_abc123",
    )
    assert selector.users == "alice@example.com,user_abc123"
