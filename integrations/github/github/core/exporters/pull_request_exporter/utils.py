from datetime import UTC, datetime
from typing import Any


def filter_prs_by_updated_at(
    prs: list[dict[str, Any]], updated_at_field: str, updated_after: datetime
) -> list[dict[str, Any]]:

    return [
        pr
        for pr in prs
        if datetime.strptime(pr[updated_at_field], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=UTC
        )
        >= updated_after
    ]
