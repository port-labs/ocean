import time
import datetime


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


def get_start_of_the_day_in_seconds_x_day_back(days_back: int) -> int:
    now = datetime.datetime.now()
    target_date = now - datetime.timedelta(days=days_back)
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(start_of_day.timestamp())


def generate_time_windows_from_interval_days(
    interval: int, start_timestamp: int
) -> list[tuple[int, int]]:
    """
    This function takes in a period of time in days and an interval in days,
    and returns a list of tuples, each containing two timestamps.
    """
    interval_seconds = interval * 24 * 60 * 60
    current_time_in_seconds = int(time.time())

    timestamps = []
    for start_time in range(start_timestamp, current_time_in_seconds, interval_seconds):
        end_date = start_time + interval_seconds
        if end_date > current_time_in_seconds:
            timestamps.append((start_time, current_time_in_seconds))
        else:
            timestamps.append((start_time, end_date))

    return timestamps
