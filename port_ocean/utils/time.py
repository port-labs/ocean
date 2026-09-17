import datetime
import re

from loguru import logger

ISO_8601_DATE_REGEX = r"^\d{4}-\d{2}-\d{2}$"
ISO_8601_DATETIME_REGEX = (
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})$"
)
ISO_8601_SELECTOR_REGEX = (
    r"^("
    r"\d{4}-\d{2}-\d{2}"
    r"|"
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})$"
    r")$"
)


def parse_selector_iso_datetime(time_str: str) -> datetime.datetime:
    """Parse an ISO 8601 date or datetime selector value as UTC.

    Date-only values (``YYYY-MM-DD``) are interpreted as UTC midnight.
    """
    stripped = time_str.strip()
    if re.fullmatch(ISO_8601_DATE_REGEX, stripped):
        return datetime.datetime.fromisoformat(f"{stripped}T00:00:00+00:00").astimezone(
            datetime.timezone.utc
        )
    return convert_str_to_utc_datetime(stripped)


def convert_str_to_utc_datetime(time_str: str) -> datetime.datetime:
    """
    Convert a string representing time to a datetime object.
    :param time_str: a string representing time in the format "2021-09-01T12:00:00Z"
    """
    aware_date = datetime.datetime.fromisoformat(time_str)
    if time_str.endswith("Z"):
        aware_date = datetime.datetime.fromisoformat(time_str.replace("Z", "+00:00"))
    return aware_date.astimezone(datetime.timezone.utc)


def convert_to_minutes(s: str) -> int:
    minutes_per_unit = {"s": 1 / 60, "m": 1, "h": 60, "d": 1440, "w": 10080}
    try:
        return int(int(s[:-1]) * minutes_per_unit[s[-1]])
    except Exception:
        logger.error(f"Failed converting string to minutes, {s}")
        raise ValueError(
            f"Invalid format. Expected a string ending with {minutes_per_unit.keys()}"
        )


def parse_interval_to_minutes(value: str | int, *, default_minutes: int = 15) -> int:
    if isinstance(value, int):
        return value
    stripped = value.strip()
    if not stripped:
        return default_minutes
    if stripped.isdigit():
        return int(stripped)
    return convert_to_minutes(stripped)


def get_next_occurrence(
    interval_seconds: int,
    start_time: datetime.datetime,
    now: datetime.datetime | None = None,
) -> datetime.datetime:
    """
    Predict the next occurrence of an event based on interval, start time, and current time.

    :param interval_minutes: Interval between occurrences in minutes.
    :param start_time: Start time of the event as a datetime object.
    :param now: Current time as a datetime object.
    :return: The next occurrence time as a datetime object.
    """

    if now is None:
        now = datetime.datetime.now(tz=datetime.timezone.utc)
    # Calculate the total seconds elapsed since the start time
    elapsed_seconds = (now - start_time).total_seconds()

    # Calculate the number of intervals that have passed
    intervals_passed = int(elapsed_seconds // interval_seconds)

    # Calculate the next occurrence time
    next_occurrence = start_time + datetime.timedelta(
        seconds=(intervals_passed + 1) * interval_seconds
    )

    return next_occurrence
