"""Query-param builders for incremental resyncs.

Each ``build_incremental_*_params`` builds the query for a run that has a cursor.
The matching full-resync builders live in ``gitlab/clients/utils.py``. Resync
handlers in ``main.py`` pick one or the other on ``sync_cursor``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from port_ocean.core.incremental.strategies import ServerSideTimestampStrategy

from gitlab.clients.utils import (
    MergeRequestState,
    build_project_params,
    parse_optional_iso_datetime,
)

# GitLab filters list endpoints server-side by the resource's updated_at.
UPDATED_AFTER_INCREMENTAL = ServerSideTimestampStrategy(param_key="updated_after")
LAST_ACTIVITY_AFTER_INCREMENTAL = ServerSideTimestampStrategy(
    param_key="last_activity_after"
)

# Dropped on incremental runs; replaced by cursor ``updated_after`` + ``order_by``.
TIMESTAMP_SELECTORS = {
    "finished_after",
    "finished_before",
    "updated_after",
    "updated_before",
}


def build_cursor_updated_after_params(
    base_params: dict[str, Any] | None,
    cursor: datetime,
) -> dict[str, Any]:
    """Drop selector timestamp filters and ``order_by``, then apply the cursor.

    Keeps the other non-None filters. ``updated_after``, ``updated_before``,
    ``finished_after``, ``finished_before`` and ``order_by`` from the selector are
    replaced by the cursor ``updated_after`` and ``order_by=updated_at``.
    """
    params = {
        key: value
        for key, value in (base_params or {}).items()
        if key not in TIMESTAMP_SELECTORS and key != "order_by" and value is not None
    }
    params = UPDATED_AFTER_INCREMENTAL.merge_params(params, cursor)
    params["order_by"] = "updated_at"
    return params


def build_incremental_projects_params(
    include_only_active_projects: bool | None,
    cursor: datetime,
) -> dict[str, Any]:
    """Query params for ``GET /projects`` on an incremental run (``last_activity_after``)."""
    return LAST_ACTIVITY_AFTER_INCREMENTAL.merge_params(
        build_project_params(include_only_active_projects=include_only_active_projects),
        cursor,
    )


def build_incremental_project_updated_params(
    include_only_active_projects: bool | None,
    cursor: datetime,
) -> dict[str, Any]:
    """Query params for ``GET /projects`` on an incremental run (``updated_after``).

    Used by the file, folder, skill and plugin resyncs.
    """
    return build_cursor_updated_after_params(
        build_project_params(include_only_active_projects=include_only_active_projects),
        cursor,
    )


def build_incremental_merge_request_params(
    state: MergeRequestState,
    cursor: datetime,
) -> dict[str, Any]:
    """Query params for ``GET /groups/{id}/merge_requests`` on an incremental run."""
    return UPDATED_AFTER_INCREMENTAL.merge_params({"state": state}, cursor)


def build_incremental_pipeline_params(
    api_query_params: dict[str, Any] | None,
    cursor: datetime,
) -> dict[str, Any]:
    """Query params for ``GET /projects/{id}/pipelines`` on an incremental run.

    The cursor replaces any ``updated_after`` set on the selector. The selector value
    is still parsed, so a malformed value raises here as it did before.
    """
    raw = dict(api_query_params or {})
    parse_optional_iso_datetime(raw.pop("updated_after", None))
    params = {key: value for key, value in raw.items() if value is not None}
    return UPDATED_AFTER_INCREMENTAL.merge_params(params, cursor)
