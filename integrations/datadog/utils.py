import time
import datetime

from loguru import logger


def get_start_of_the_month_in_seconds_x_months_back(months_back: int) -> int:
    """
    Calculate the timestamp for the start of the month 'months_back'.
    """
    now = datetime.datetime.now()
    month_number = (now.month - months_back) % 12
    is_year_change = months_back > now.month
    year_change = 1 if is_year_change else 0
    start_of_month = datetime.datetime(now.year - year_change, month_number, 1)
    return int(start_of_month.timestamp())


def transform_period_of_time_in_days_to_timestamps(
    interval: int, period_of_time_in_months: int = 12
) -> list[tuple[int, int]]:
    """
    This function takes in a period of time in days and an interval in days,
    and returns a list of tuples, each containing two timestamps.
    """
    interval_seconds = interval * 24 * 60 * 60
    period_time_to_go_back_in_seconds = get_start_of_the_month_in_seconds_x_months_back(
        period_of_time_in_months
    )
    current_time_in_seconds = int(time.time())

    logger.info(
        f"Generating timestamps for the period of time {period_of_time_in_months} years ago"
    )
    timestamps = []
    for start_time in range(
        period_time_to_go_back_in_seconds, current_time_in_seconds, interval_seconds
    ):
        end_date = start_time + interval_seconds
        if end_date > current_time_in_seconds:
            timestamps.append((start_time, current_time_in_seconds))
        else:
            timestamps.append((start_time, end_date))

    return timestamps
