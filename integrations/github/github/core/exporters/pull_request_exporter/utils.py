from datetime import UTC, datetime, timedelta
from typing import Any


def filter_prs_by_updated_at(
    prs: list[dict[str, Any]], updated_at_field: str, since: int
) -> list[dict[str, Any]]:
    cutoff = datetime.now(UTC) - timedelta(days=since)

    return [
        pr
        for pr in prs
        if datetime.strptime(pr[updated_at_field], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=UTC
        )
        >= cutoff
    ]
