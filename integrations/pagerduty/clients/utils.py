from datetime import datetime, timedelta


def get_date_range_for_last_n_months(n: int) -> tuple[str, str]:
    now = datetime.utcnow()
    start_date = (now - timedelta(days=30 * n)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )  # using ISO 8601 format
    end_date = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    return (start_date, end_date)


def get_date_range_for_upcoming_n_months(n: int) -> tuple[str, str]:
    now = datetime.utcnow()
    start_date = now.strftime("%Y-%m-%dT%H:%M:%SZ")  # using ISO 8601 format
    end_date = (now + timedelta(days=30 * n)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (start_date, end_date)
