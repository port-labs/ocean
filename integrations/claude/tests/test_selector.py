import pytest
from pydantic import ValidationError

from integration import ClaudeCodeAnalyticsSelector


def _make_selector(**kwargs: object) -> ClaudeCodeAnalyticsSelector:
    return ClaudeCodeAnalyticsSelector(**{"query": "true", **kwargs})


# ---------------------------------------------------------------------------
# Valid configurations — exactly one field provided
# ---------------------------------------------------------------------------


def test_selector_accepts_time_frame_only() -> None:
    sel = _make_selector(timeFrame=30)
    assert sel.time_frame == 30
    assert sel.starting_date is None


def test_selector_accepts_starting_date_only() -> None:
    sel = _make_selector(startingDate="2026-01-01")
    assert sel.starting_date == "2026-01-01"
    assert sel.time_frame is None


# ---------------------------------------------------------------------------
# Invalid configurations — mutual exclusion enforced
# ---------------------------------------------------------------------------


def test_selector_rejects_neither_field() -> None:
    with pytest.raises(ValidationError, match="Either 'startingDate' or 'timeFrame'"):
        _make_selector()


def test_selector_rejects_both_fields() -> None:
    with pytest.raises(
        ValidationError, match="'startingDate' and 'timeFrame' are mutually exclusive"
    ):
        _make_selector(startingDate="2026-01-01", timeFrame=30)


# ---------------------------------------------------------------------------
# Field-level validation
# ---------------------------------------------------------------------------


def test_selector_rejects_non_positive_time_frame() -> None:
    with pytest.raises(ValidationError):
        _make_selector(timeFrame=0)
