import time


def transform_period_of_time_in_days_to_timestamps(
    period_of_time_in_days: int,
) -> tuple[int, int]:
    """
    This function takes in a period of time in days and returns a tuple of two timestamps.
    """
    start_time = int(time.time() - (period_of_time_in_days * 24 * 60 * 60))
    end_time = int(time.time())
    return start_time, end_time
