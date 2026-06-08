from datetime import datetime, timedelta, timezone

from core.options import ListCursorAdminOptions, ListCursorAnalyticsOptions

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 500 # Cursor's paginated endpoints accept large page sizes


def _parse_relative_days(relative_date: str) -> int:
    return int(relative_date.removesuffix("d"))


def build_analytics_options(
    start_date: str,
    end_date: str,
) -> ListCursorAnalyticsOptions:
    # Analytics/AI Code Tracking endpoints accept Cursor's relative `Xd` format.
    start_days = _parse_relative_days(start_date)
    end_days = _parse_relative_days(end_date)
    return {
        "startDate": f"{start_days}d",
        "endDate": f"{end_days}d",
        "page": DEFAULT_PAGE,
        "pageSize": DEFAULT_PAGE_SIZE,
    }


def build_admin_options(
    start_date: str,
    end_date: str,
) -> ListCursorAdminOptions:
    # Admin endpoints expect epoch-millisecond bounds.
    now = datetime.now(timezone.utc)
    start_datetime = now - timedelta(days=_parse_relative_days(start_date))
    end_datetime = now - timedelta(days=_parse_relative_days(end_date))

    return {
        "startDate": int(start_datetime.timestamp() * 1000),
        "endDate": int(end_datetime.timestamp() * 1000),
        "page": DEFAULT_PAGE,
        "pageSize": DEFAULT_PAGE_SIZE,
    }
