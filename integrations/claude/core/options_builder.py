from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from loguru import logger

from core.options import (
    ClaudeAIContextWindow,
    ClaudeAIGroupBy,
    ClaudeAIInferenceGeo,
    ClaudeAIProduct,
    ClaudeAISpeed,
    ClaudePlatformUsageGroupBy,
    ListPlatformCodeAnalyticsOptions,
    ListPlatformCostReportOptions,
    ListPlatformUsageReportOptions,
    ListUserActivityOptions,
    ListUserReportOptions,
)

# The analytics, users and code-analytics endpoints page by record count and
# accept up to 1000 rows per page. Request the max to minimise the number of round trips
ANALYTICS_PAGE_SIZE = 1000

# The Claude Platform usage/cost reports page by *time bucket*, not by record
# count, so their max ``limit`` depends on the bucket width. Request the max
# for the chosen granularity.
PLATFORM_BUCKET_LIMITS: dict[str, int] = {"1m": 1440, "1h": 168, "1d": 31}

# The Claude AI (Enterprise) analytics endpoints only expose data from this
# date onwards, and a usage/cost range may span at most 31 days.
ANALYTICS_MIN_DATE = datetime(2026, 1, 1, tzinfo=timezone.utc)
ANALYTICS_MAX_RANGE_DAYS = 31

# The users endpoint rejects any date newer than this many days ago with a 400
# ("date must be at least 3 days ago to ensure accuracy of data").
USER_ACTIVITY_DATA_LAG_DAYS = 3

# Default look-back window applied when neither startingDate nor timeFrame is set.
DEFAULT_USER_ACTIVITY_TIME_FRAME = 30

_RFC3339_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_today() -> date:
    return _utc_now().date()


def _parse_rfc3339(value: str) -> datetime:
    """Parse an RFC-3339 timestamp, treating naive values as UTC.

    Sanitizes supplied dates. A trailing ``Z`` is normalized and a
    timestamp without timezone information is assumed to be UTC.
    """
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_rfc3339(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime(_RFC3339_FORMAT)


def resolve_analytics_range(
    starting_at: str,
    ending_at: str | None = None,
) -> tuple[str, str]:
    """Clamp an analytics date range to the limits Anthropic enforces.

    * ``starting_at`` is floored to no earlier than 2026-01-01 and no earlier
      than ``ANALYTICS_MAX_RANGE_DAYS`` ago.
    * ``ending_at`` defaults to now and is capped so the range never exceeds
      ``ANALYTICS_MAX_RANGE_DAYS``.

    Returns RFC-3339 timestamps (with ``Z``) safe to send to the API.
    """
    now = _utc_now()
    end = _parse_rfc3339(ending_at) if ending_at else now
    end = min(end, now)

    earliest_allowed = max(
        ANALYTICS_MIN_DATE, now - timedelta(days=ANALYTICS_MAX_RANGE_DAYS)
    )
    start = max(_parse_rfc3339(starting_at), earliest_allowed)

    if end <= start:
        end = now

    # Keep the window within the allowed span.
    if end - start > timedelta(days=ANALYTICS_MAX_RANGE_DAYS):
        start = end - timedelta(days=ANALYTICS_MAX_RANGE_DAYS)

    if start != _parse_rfc3339(starting_at):
        logger.info(
            f"Clamped analytics starting_at from '{starting_at}' to "
            f"'{_format_rfc3339(start)}' to respect Anthropic's limits."
        )

    return _format_rfc3339(start), _format_rfc3339(end)


# Claude Platform option builders


def build_platform_usage_options(
    starting_date: str,
    bucket_width: Literal["1m", "1h", "1d"],
    group_by: Sequence[ClaudePlatformUsageGroupBy],
    limit: int | None = None,
) -> ListPlatformUsageReportOptions:
    options: ListPlatformUsageReportOptions = {
        "starting_at": starting_date,
        "limit": limit or PLATFORM_BUCKET_LIMITS[bucket_width],
        "bucket_width": bucket_width,
    }
    if group_by:
        options["group_by"] = list(group_by)
    return options


def build_platform_cost_options(
    starting_date: str,
    bucket_width: Literal["1d"],
    limit: int | None = None,
) -> ListPlatformCostReportOptions:
    return {
        "starting_at": starting_date,
        "limit": limit or PLATFORM_BUCKET_LIMITS[bucket_width],
        "bucket_width": bucket_width,
    }


def build_platform_code_analytics_options(
    starting_date: str,
    limit: int = ANALYTICS_PAGE_SIZE,
) -> ListPlatformCodeAnalyticsOptions:
    return {
        "starting_at": starting_date,
        "limit": limit,
    }


def get_code_analytics_dates(
    starting_date: str | None,
    time_frame: int | None,
) -> list[str]:
    """Return the ordered list of YYYY-MM-DD dates to query.

    Exactly one of starting_date / time_frame must be provided.
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


# Claude AI (Enterprise) option builders


def get_user_activity_dates(
    starting_date: str | None,
    time_frame: int | None,
) -> list[str]:
    """Return the ordered list of YYYY-MM-DD dates for the users endpoint.

    The users endpoint reports a single day at a time. Dates are clamped to the
    window Anthropic accepts: no earlier than 2026-01-01 (the earliest data
    exposed) and no newer than ``USER_ACTIVITY_DATA_LAG_DAYS`` days ago (the
    endpoint rejects more recent dates with a 400).
    """
    today = _utc_today()
    min_date = ANALYTICS_MIN_DATE.date()
    latest = today - timedelta(days=USER_ACTIVITY_DATA_LAG_DAYS)

    # When neither field is provided, fall back to the default look-back window.
    if time_frame is None and starting_date is None:
        time_frame = DEFAULT_USER_ACTIVITY_TIME_FRAME

    if time_frame is not None:
        start = latest - timedelta(days=time_frame - 1)
    else:
        assert starting_date is not None  # guaranteed by the default-fill above
        start = date.fromisoformat(starting_date)

    if start < min_date:
        logger.info(
            f"Clamped user-activity start from '{start.isoformat()}' to "
            f"'{min_date.isoformat()}' (earliest available data)."
        )
        start = min_date

    if latest < min_date:
        logger.warning(
            "No Claude AI user-activity dates available yet "
            f"(latest queryable date '{latest.isoformat()}' precedes the "
            f"earliest available data '{min_date.isoformat()}')."
        )
        return []

    num_days = (latest - start).days + 1
    if num_days <= 0:
        logger.warning(
            f"Computed user-activity start '{start.isoformat()}' is newer than "
            f"the latest queryable date '{latest.isoformat()}' — no dates to "
            "fetch. The users endpoint only returns data at least "
            f"{USER_ACTIVITY_DATA_LAG_DAYS} days old."
        )
        return []
    return [(start + timedelta(days=i)).isoformat() for i in range(num_days)]


def build_user_activity_options(
    date: str,
    limit: int = ANALYTICS_PAGE_SIZE,
) -> ListUserActivityOptions:
    return {
        "date": date,
        "limit": limit,
    }


def build_user_report_options(
    starting_at: str,
    ending_at: str | None,
    exclude_deleted_users: bool,
    products: Sequence[ClaudeAIProduct],
    models: Sequence[str],
    group_by: Sequence[ClaudeAIGroupBy],
    context_windows: Sequence[ClaudeAIContextWindow],
    inference_geos: Sequence[ClaudeAIInferenceGeo],
    speeds: Sequence[ClaudeAISpeed],
    limit: int = ANALYTICS_PAGE_SIZE,
) -> ListUserReportOptions:
    """Build shared options for the user usage and cost report endpoints."""
    start, end = resolve_analytics_range(starting_at, ending_at)
    options: ListUserReportOptions = {
        "starting_at": start,
        "ending_at": end,
        "limit": limit,
        "exclude_deleted_users": exclude_deleted_users,
    }
    if products:
        options["products"] = list(products)
    if models:
        options["models"] = list(models)
    if group_by:
        options["group_by"] = list(group_by)
    if context_windows:
        options["context_windows"] = list(context_windows)
    if inference_geos:
        options["inference_geos"] = list(inference_geos)
    if speeds:
        options["speeds"] = list(speeds)
    return options
