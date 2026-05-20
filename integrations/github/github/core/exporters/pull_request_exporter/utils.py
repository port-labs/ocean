from datetime import UTC, datetime
from typing import Any


def filter_prs_by_updated_at(
    prs: list[dict[str, Any]], updated_at_field: str, updated_after: datetime
) -> list[dict[str, Any]]:

    return [
        pr
        for pr in prs
        if (
            (updated_at := pr.get(updated_at_field))
            and datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            >= updated_after
        )
    ]
