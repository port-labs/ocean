from datetime import datetime
from typing import Any

from port_ocean.core.incremental.strategies import ServerSideTimestampStrategy

GitlabQueryParams = dict[str, Any]

GITLAB_INCREMENTAL = ServerSideTimestampStrategy(
    param_key="updated_after",
    date_format="%Y-%m-%dT%H:%M:%SZ",
)


def with_incremental_cursor(
    params: GitlabQueryParams,
    cursor: datetime | None,
) -> GitlabQueryParams:
    """Inject ``updated_after`` from the Ocean incremental cursor when present."""
    return GITLAB_INCREMENTAL.merge_params(params, cursor)


def with_project_incremental_cursor(
    params: GitlabQueryParams,
    cursor: datetime | None,
    *,
    has_search_queries: bool,
) -> GitlabQueryParams:
    """Apply project incremental filters.

    GitLab requires ``order_by=updated_at`` alongside ``updated_after``.
    Search-query paths cannot use the list-endpoint incremental filter, so the
    cursor is ignored when ``has_search_queries`` is true.
    """
    if cursor is None or has_search_queries:
        return params

    result = GITLAB_INCREMENTAL.merge_params(params, cursor)
    result["order_by"] = "updated_at"
    return result


def build_merge_request_params(
    state: str,
    cursor: datetime | None,
    lookback_updated_after: datetime,
) -> GitlabQueryParams:
    """Build MR list params for a single state.

    On incremental sync the cursor applies to every state (including ``opened``).
    On full resync, only non-``opened`` states use the selector lookback window.
    """
    params: GitlabQueryParams = {"state": state}
    if cursor is not None:
        return GITLAB_INCREMENTAL.merge_params(params, cursor)
    if state != "opened":
        params["updated_after"] = lookback_updated_after
    return params
