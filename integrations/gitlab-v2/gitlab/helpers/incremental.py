from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from port_ocean.core.incremental.strategies import ServerSideTimestampStrategy

from gitlab.clients.options import IssueOptions

# GitLab filters group issues server-side by the issue's updated_at.
ISSUE_INCREMENTAL = ServerSideTimestampStrategy(param_key="updated_after")


def resolve_effective_datetime(
    cursor: datetime | None,
    selector_value: datetime | None,
) -> datetime | None:
    """Prefer the incremental cursor over a selector-derived datetime."""
    if cursor is not None:
        return cursor
    return selector_value


def build_issue_params(
    options: IssueOptions,
    updated_after: Optional[datetime],
) -> dict[str, Any]:
    """Query params for ``GET /groups/{id}/issues``.

    ``updated_after`` should already be resolved via
    :func:`resolve_effective_datetime` (cursor wins over selector), matching
    GitHub's issue exporter which receives a single effective datetime and
    merges it with :class:`ServerSideTimestampStrategy`.
    """
    params = {
        key: value
        for key, value in options.items()
        if value is not None and key != "updated_after"
    }
    return ISSUE_INCREMENTAL.merge_params(params, updated_after)
