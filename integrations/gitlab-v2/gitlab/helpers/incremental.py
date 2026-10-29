from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from port_ocean.core.incremental.strategies import ServerSideTimestampStrategy

from gitlab.clients.options import IssueOptions

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
MergeRequestState = Literal["opened", "closed", "merged"]


def resolve_effective_datetime(
    cursor: datetime | None,
    selector_value: datetime | None,
) -> datetime | None:
    """Prefer the incremental cursor over a selector-derived datetime."""
    if cursor is not None:
        return cursor
    return selector_value


def build_project_list_params(
    base_params: dict[str, Any],
    cursor: datetime | None,
) -> dict[str, Any]:
    """Query params for ``GET /projects``."""
    return LAST_ACTIVITY_AFTER_INCREMENTAL.merge_params(base_params, cursor)


def build_issue_params(
    options: IssueOptions,
    updated_after: Optional[datetime],
) -> dict[str, Any]:
    """Query params for ``GET /groups/{id}/issues``."""
    params = {
        key: value
        for key, value in options.items()
        if value is not None and key != "updated_after"
    }
    return UPDATED_AFTER_INCREMENTAL.merge_params(params, updated_after)


def build_merge_request_params(
    state: MergeRequestState,
    cursor: datetime | None,
    lookback_updated_after: datetime,
) -> dict[str, Any]:
    """Query params for ``GET /groups/{id}/merge_requests``."""
    params: dict[str, Any] = {"state": state}
    effective = resolve_effective_datetime(
        cursor,
        lookback_updated_after if state != "opened" else None,
    )
    return UPDATED_AFTER_INCREMENTAL.merge_params(params, effective)


def _parse_optional_iso_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def build_pipeline_params(
    api_query_params: dict[str, Any] | None,
    cursor: datetime | None,
) -> dict[str, Any]:
    """Query params for ``GET /projects/{id}/pipelines``."""
    return merge_updated_after_params(api_query_params, cursor)


def build_cursor_updated_after_params(
    api_query_params: dict[str, Any] | None,
    cursor: datetime,
) -> dict[str, Any]:
    """Drop selector timestamp filters and ``order_by``, then apply the cursor.

    Keeps non-timestamp filters. ``updated_after``, ``updated_before``,
    ``finished_after``, ``finished_before``, and ``order_by`` from the selector
    are replaced by the cursor ``updated_after`` and ``order_by=updated_at``.
    """
    params = {
        key: value
        for key, value in (api_query_params or {}).items()
        if key not in TIMESTAMP_SELECTORS and key != "order_by" and value is not None
    }
    params = UPDATED_AFTER_INCREMENTAL.merge_params(params, cursor)
    params["order_by"] = "updated_at"
    return params


def build_incremental_project_params(
    base_params: dict[str, Any],
    cursor: datetime | None,
) -> dict[str, Any]:
    """Project-list params for an incremental run.

    A cursor replaces selector timestamp filters with ``updated_after`` and
    ``order_by=updated_at``. A full resync keeps ``base_params``.
    """
    if cursor is None:
        return base_params
    return build_cursor_updated_after_params(base_params, cursor)


def build_deployment_params(
    api_query_params: dict[str, Any] | None,
    cursor: datetime,
) -> dict[str, Any]:
    """Incremental query params for ``GET /projects/{id}/deployments``."""
    return build_cursor_updated_after_params(api_query_params, cursor)


def merge_updated_after_params(
    api_query_params: dict[str, Any] | None,
    cursor: datetime | None,
) -> dict[str, Any]:
    raw = dict(api_query_params or {})
    selector_updated_after = _parse_optional_iso_datetime(
        raw.pop("updated_after", None)
    )
    params = {key: value for key, value in raw.items() if value is not None}
    effective = resolve_effective_datetime(cursor, selector_updated_after)
    return UPDATED_AFTER_INCREMENTAL.merge_params(params, effective)
