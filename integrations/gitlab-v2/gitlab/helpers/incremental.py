from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from port_ocean.core.incremental.strategies import (
    ClientSideCutoffStrategy,
    ServerSideTimestampStrategy,
)

from gitlab.clients.options import IssueOptions

# GitLab filters list endpoints server-side by the resource's updated_at.
UPDATED_AFTER_INCREMENTAL = ServerSideTimestampStrategy(param_key="updated_after")
LAST_ACTIVITY_AFTER_INCREMENTAL = ServerSideTimestampStrategy(
    param_key="last_activity_after"
)

# Tags API has no updated_after; order newest-first and stop on created_at.
# Lightweight tags often omit created_at — those are kept and do not trigger early-stop.
TAG_INCREMENTAL = ClientSideCutoffStrategy(
    stop_field="created_at",
    query_params={"order_by": "updated", "sort": "desc"},
)

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
    """Query params for ``GET /projects`` using ``last_activity_after``."""
    return LAST_ACTIVITY_AFTER_INCREMENTAL.merge_params(base_params, cursor)


def build_project_updated_after_params(
    base_params: dict[str, Any],
    cursor: datetime | None,
) -> dict[str, Any]:
    """Query params for ``GET /projects`` using ``updated_after``.

    GitLab requires ``order_by=updated_at`` for ``updated_after`` to take effect.
    Used by release incremental: gate projects, then fetch all releases (releases
    have no reliable change timestamp).
    """
    params = UPDATED_AFTER_INCREMENTAL.merge_params(base_params, cursor)
    if "updated_after" in params:
        params["order_by"] = "updated_at"
    return params


def build_tag_list_params(cursor: datetime | None) -> dict[str, Any]:
    """Query params for ``GET /projects/:id/repository/tags``.

    GitLab has no server-side time filter for tags; on incremental runs this
    requests newest-first ordering so callers can early-stop with
    ``TAG_INCREMENTAL``.
    """
    return TAG_INCREMENTAL.merge_params({}, cursor)


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


def build_deployment_params(
    api_query_params: dict[str, Any] | None,
    cursor: datetime | None,
) -> dict[str, Any]:
    """Query params for ``GET /projects/{id}/deployments``."""
    raw = dict(api_query_params or {})
    if "finished_after" in raw or "finished_before" in raw:
        # GitLab rejects mixing a finished window with updated_after.
        raw.pop("updated_after", None)
        params = {key: value for key, value in raw.items() if value is not None}
        params["order_by"] = "finished_at"
        return params

    params = merge_updated_after_params(api_query_params, cursor)
    if "updated_after" in params:
        params["order_by"] = "updated_at"
    return params


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
