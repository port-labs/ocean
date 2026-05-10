from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from loguru import logger

from core.options import (
    ClaudeUsageGroupBy,
    ListClaudeCodeAnalyticsOptions,
    ListClaudeCostReportOptions,
    ListClaudeUsageReportOptions,
)

DEFAULT_PAGE_SIZE = 30


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def build_usage_options(
    starting_date: str,
    bucket_width: Literal["1m", "1h", "1d"],
    group_by: Sequence[ClaudeUsageGroupBy],
    limit: int = DEFAULT_PAGE_SIZE,
) -> ListClaudeUsageReportOptions:
    options: ListClaudeUsageReportOptions = {
        "starting_at": starting_date,
        "limit": limit,
        "bucket_width": bucket_width,
    }
    if group_by:
        options["group_by"] = list(group_by)
    return options


def build_cost_options(
    starting_date: str,
    bucket_width: Literal["1d"],
    limit: int = DEFAULT_PAGE_SIZE,
) -> ListClaudeCostReportOptions:
    return {
        "starting_at": starting_date,
        "limit": limit,
        "bucket_width": bucket_width,
    }


def build_code_analytics_options(
    starting_date: str,
    limit: int = DEFAULT_PAGE_SIZE,
) -> ListClaudeCodeAnalyticsOptions:
    return {
        "starting_at": starting_date,
        "limit": limit,
    }


def get_code_analytics_dates(
    starting_date: str | None,
    time_frame: int | None,
) -> list[str]:
    """Return the ordered list of YYYY-MM-DD dates to query.

    Exactly one of starting_date / time_frame must be non-None
    (enforced by ClaudeCodeAnalyticsSelector's validator).
    """
    today = _utc_today()
    if time_frame is not None:
        return [
            (today - timedelta(days=i)).isoformat()
            for i in range(time_frame - 1, -1, -1)
        ]
    start = date.fromisoformat(starting_date)  # type: ignore[arg-type]
    num_days = (today - start).days + 1
    if num_days <= 0:
        logger.warning(
            f"startingDate '{starting_date}' is in the future — no dates to fetch"
        )
        return []
    return [(start + timedelta(days=i)).isoformat() for i in range(num_days)]
