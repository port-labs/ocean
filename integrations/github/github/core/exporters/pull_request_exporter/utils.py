from datetime import UTC, datetime
from typing import Any


def filter_prs_by_date(
    prs: list[dict[str, Any]], date_field: str, cutoff: datetime
) -> list[dict[str, Any]]:

    return [
        pr
        for pr in prs
        if (
            (value := pr.get(date_field))
            and datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            >= cutoff
        )
    ]
