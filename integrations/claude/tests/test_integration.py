import pytest
from pydantic import ValidationError

from integration import (
    ClaudeAIUserActivitySelector,
    ClaudeAIUserReportSelector,
    ClaudePlatformCodeAnalyticsResourceConfig,
    ClaudePlatformCodeAnalyticsSelector,
    ClaudePlatformCostRecordResourceConfig,
    ClaudePlatformUsageRecordResourceConfig,
)

_MINIMAL_PORT = {"entity": {"mappings": {"identifier": ".id", "blueprint": '"bp"'}}}

# ---------------------------------------------------------------------------
# Claude Platform code analytics selector (date mutual exclusion)
# ---------------------------------------------------------------------------


def test_platform_code_selector_accepts_time_frame_only() -> None:
    sel = ClaudePlatformCodeAnalyticsSelector(query="true", timeFrame=30)
    assert sel.time_frame == 30
    assert sel.starting_date is None


def test_platform_code_selector_accepts_starting_date_only() -> None:
    sel = ClaudePlatformCodeAnalyticsSelector(query="true", startingDate="2026-01-01")
    assert sel.starting_date == "2026-01-01"
    assert sel.time_frame is None


def test_platform_code_selector_rejects_both_fields() -> None:
    with pytest.raises(
        ValidationError, match="'startingDate' and 'timeFrame' are mutually exclusive"
    ):
        ClaudePlatformCodeAnalyticsSelector(
            query="true", startingDate="2026-01-01", timeFrame=30
        )


# ---------------------------------------------------------------------------
# Claude AI user activity selector
# ---------------------------------------------------------------------------


def test_user_activity_selector_allows_neither_field() -> None:
    # A 30-day default is applied downstream, so neither field is required.
    sel = ClaudeAIUserActivitySelector(query="true")
    assert sel.time_frame is None
    assert sel.starting_date is None


def test_user_activity_selector_accepts_starting_date_only() -> None:
    sel = ClaudeAIUserActivitySelector(query="true", startingDate="2026-02-01")
    assert sel.starting_date == "2026-02-01"
    assert sel.time_frame is None


def test_user_activity_selector_rejects_both_fields() -> None:
    with pytest.raises(
        ValidationError, match="'startingDate' and 'timeFrame' are mutually exclusive"
    ):
        ClaudeAIUserActivitySelector(
            query="true", startingDate="2026-01-01", timeFrame=30
        )


def test_user_activity_selector_rejects_non_positive_time_frame() -> None:
    with pytest.raises(ValidationError):
        ClaudeAIUserActivitySelector(query="true", timeFrame=0)


def test_user_activity_selector_rejects_malformed_starting_date() -> None:
    with pytest.raises(ValidationError):
        ClaudeAIUserActivitySelector(query="true", startingDate="not-a-date")


# ---------------------------------------------------------------------------
# Claude AI user report selector (shared by usage and cost)
# ---------------------------------------------------------------------------


def test_user_report_selector_defaults() -> None:
    sel = ClaudeAIUserReportSelector(query="true")
    assert sel.starting_at == "2026-01-01T00:00:00Z"
    assert sel.exclude_deleted_users is False
    assert sel.products == []


def test_user_report_selector_rejects_unknown_product() -> None:
    with pytest.raises(ValidationError):
        ClaudeAIUserReportSelector(query="true", products=["not_a_product"])  # type: ignore[list-item]


def test_user_report_selector_rejects_malformed_starting_at() -> None:
    with pytest.raises(ValidationError):
        ClaudeAIUserReportSelector(query="true", startingAt="2026-01-01")


# ---------------------------------------------------------------------------
# Backwards compatibility — platform configs accept the legacy kind aliases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "config_cls,new_kind,legacy_kind,selector",
    [
        (
            ClaudePlatformUsageRecordResourceConfig,
            "claude-platform-usage-record",
            "claude-usage-record",
            {"query": "true"},
        ),
        (
            ClaudePlatformCostRecordResourceConfig,
            "claude-platform-cost-record",
            "claude-cost-record",
            {"query": "true"},
        ),
        (
            ClaudePlatformCodeAnalyticsResourceConfig,
            "claude-platform-code-analytics",
            "claude-code-analytics",
            {"query": "true", "timeFrame": 30},
        ),
    ],
)
def test_platform_config_accepts_new_and_legacy_kinds(
    config_cls: type, new_kind: str, legacy_kind: str, selector: dict[str, object]
) -> None:
    for kind in (new_kind, legacy_kind):
        config = config_cls(kind=kind, selector=selector, port=_MINIMAL_PORT)
        assert config.kind == kind
