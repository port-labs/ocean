from collections.abc import Sequence
from datetime import date
from typing import Literal

from core.options import (
    ClaudeUsageGroupBy,
    ListClaudeCodeAnalyticsOptions,
    ListClaudeCostReportOptions,
    ListClaudeUsageReportOptions,
)

DEFAULT_PAGE_SIZE = 30


def _today_iso() -> str:
    return date.today().isoformat()


def _today_utc() -> str:
    return f"{_today_iso()}T00:00:00Z"


def build_usage_options(
    starting_date: str | None,
    bucket_width: Literal["1m", "1h", "1d"],
    group_by: Sequence[ClaudeUsageGroupBy],
    limit: int = DEFAULT_PAGE_SIZE,
) -> ListClaudeUsageReportOptions:
    options: ListClaudeUsageReportOptions = {
        "starting_at": starting_date or _today_utc(),
        "limit": limit,
        "bucket_width": bucket_width,
    }
    if group_by:
        options["group_by"] = list(group_by)
    return options


def build_cost_options(
    starting_date: str | None,
    bucket_width: Literal["1d"],
    limit: int = DEFAULT_PAGE_SIZE,
) -> ListClaudeCostReportOptions:
    return {
        "starting_at": starting_date or _today_utc(),
        "limit": limit,
        "bucket_width": bucket_width,
    }


def build_code_analytics_options(
    starting_date: str | None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> ListClaudeCodeAnalyticsOptions:
    return {
        "starting_at": starting_date or _today_iso(),
        "limit": limit,
    }
