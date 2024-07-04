import time
import datetime

from loguru import logger


def start_of_month_n_years_ago(years_back: int) -> int:
    """
    Calculate the timestamp for the start of the month 'years_back' years ago.
    """
    now = datetime.datetime.now()
    start_of_month = datetime.datetime(now.year - years_back, now.month, 1)
    return int(start_of_month.timestamp())


def transform_period_of_time_in_days_to_timestamps(
    interval: int, period_of_time_in_years: int = 1
) -> list[tuple[int, int]]:
    """
    This function takes in a period of time in days and an interval in days,
    and returns a list of tuples, each containing two timestamps.
    """
    interval_seconds = interval * 24 * 60 * 60
    period_time_to_go_back_in_seconds = start_of_month_n_years_ago(
        period_of_time_in_years
    )
    current_time = int(time.time())

    logger.info(
        f"Generating timestamps for the period of time {period_of_time_in_years} years ago"
    )
    timestamps = []
    for start_time in range(
        period_time_to_go_back_in_seconds, current_time, interval_seconds
    ):
        end_date = start_time + interval_seconds
        if end_date > current_time:
            timestamps.append((start_time, current_time))
        else:
            timestamps.append((start_time, start_time + interval_seconds))

    return timestamps
