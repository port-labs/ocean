from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from loguru import logger

from core.options import (
    ClaudeCostGroupBy,
    ClaudeUsageGroupBy,
    ListClaudeActivitySummaryOptions,
    ListClaudeCostReportOptions,
    ListClaudeUsageReportOptions,
    ListClaudeUserActivityOptions,
    ListClaudeUserCostReportOptions,
    ListClaudeUserUsageReportOptions,
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
    group_by: Sequence[ClaudeCostGroupBy] = (),
    limit: int = DEFAULT_PAGE_SIZE,
) -> ListClaudeCostReportOptions:
    options: ListClaudeCostReportOptions = {
        "starting_at": starting_date,
        "limit": limit,
        "bucket_width": bucket_width,
    }
    if group_by:
        options["group_by"] = list(group_by)
    return options


def build_user_activity_options(
    date: str,
    limit: int = DEFAULT_PAGE_SIZE,
) -> ListClaudeUserActivityOptions:
    return {
        "date": date,
        "limit": limit,
    }


def build_activity_summary_options(
    starting_date: str,
    ending_date: str | None = None,
) -> ListClaudeActivitySummaryOptions:
    options: ListClaudeActivitySummaryOptions = {"starting_date": starting_date}
    if ending_date:
        options["ending_date"] = ending_date
    return options


def build_user_usage_report_options(
    starting_date: str,
    ending_date: str | None = None,
    group_by: Sequence[ClaudeUsageGroupBy] = (),
    order_by: Literal[
        "total_tokens", "output_tokens", "uncached_input_tokens"
    ] = "total_tokens",
    limit: int = DEFAULT_PAGE_SIZE,
) -> ListClaudeUserUsageReportOptions:
    options: ListClaudeUserUsageReportOptions = {
        "starting_at": starting_date,
        "limit": limit,
        "order_by": order_by,
    }
    if ending_date:
        options["ending_at"] = ending_date
    if group_by:
        options["group_by"] = list(group_by)
    return options


def build_user_cost_report_options(
    starting_date: str,
    ending_date: str | None = None,
    group_by: Sequence[ClaudeCostGroupBy] = (),
    order_by: Literal["amount", "list_amount"] = "amount",
    limit: int = DEFAULT_PAGE_SIZE,
) -> ListClaudeUserCostReportOptions:
    options: ListClaudeUserCostReportOptions = {
        "starting_at": starting_date,
        "limit": limit,
        "order_by": order_by,
    }
    if ending_date:
        options["ending_at"] = ending_date
    if group_by:
        options["group_by"] = list(group_by)
    return options


def get_daily_dates(
    starting_date: str | None,
    time_frame: int | None,
) -> list[str]:
    """Return ordered YYYY-MM-DD date strings to query one-at-a-time.

    Exactly one of starting_date / time_frame must be non-None
    (enforced by the selector validator).
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
