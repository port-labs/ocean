from datetime import datetime
from typing import Any, TypeAlias

from port_ocean.core.incremental.strategies import (
    ClientSideCutoffStrategy,
    ServerSideTimestampStrategy,
)

GitlabQueryParams: TypeAlias = dict[str, Any]
GitlabResource: TypeAlias = dict[str, Any]

GITLAB_INCREMENTAL = ServerSideTimestampStrategy(
    param_key="updated_after",
    date_format="%Y-%m-%dT%H:%M:%SZ",
)

# Tags are returned newest-first by default (order_by=updated, sort=desc).
# Lightweight tags have created_at=null; we fall back to commit.committed_date.
TAG_INCREMENTAL = ClientSideCutoffStrategy(stop_field="created_at")

def with_incremental_cursor(
    params: GitlabQueryParams,
    cursor: datetime | None,
) -> GitlabQueryParams:
    """Inject ``updated_after`` when an incremental cursor is active."""
    return GITLAB_INCREMENTAL.merge_params(params, cursor)


def with_project_incremental_cursor(
    params: GitlabQueryParams,
    cursor: datetime | None,
    *,
    has_search_queries: bool,
) -> GitlabQueryParams:
    """Apply project-specific incremental filters.

    GitLab requires ``order_by=updated_at`` alongside ``updated_after``.
    Search-query paths bypass the list-endpoint filter entirely.
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

    Incremental: cursor applies to every state (including ``opened``).
    Full resync: only non-``opened`` states use the selector lookback window.
    """
    params: GitlabQueryParams = {"state": state}
    if cursor is not None:
        return GITLAB_INCREMENTAL.merge_params(params, cursor)
    if state != "opened":
        params["updated_after"] = lookback_updated_after
    return params


def ensure_tag_created_at(tag: GitlabResource) -> GitlabResource:
    """Backfill ``created_at`` from the commit date for lightweight tags."""
    if tag.get("created_at"):
        return tag
    committed_date = (tag.get("commit") or {}).get("committed_date")
    if not committed_date:
        return tag
    return {**tag, "created_at": committed_date}
