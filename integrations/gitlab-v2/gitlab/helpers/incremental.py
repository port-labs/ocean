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

# Timestamp selectors, each requiring the matching ``order_by`` on GitLab's side.
DEPLOYMENT_TIMESTAMP_ORDER_BY = {
    "finished_after": "finished_at",
    "finished_before": "finished_at",
    "updated_after": "updated_at",
    "updated_before": "updated_at",
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


def _with_timestamp_order_by(params: dict[str, Any]) -> dict[str, Any]:
    for key, order_by in DEPLOYMENT_TIMESTAMP_ORDER_BY.items():
        if key in params:
            params["order_by"] = order_by
            break
    return params


def build_deployment_params(
    api_query_params: dict[str, Any] | None,
    cursor: datetime | None,
) -> dict[str, Any]:
    """Query params for ``GET /projects/{id}/deployments``.

    Incremental (cursor set): selector timestamp filters are ignored and only the
    cursor's timestamp param is sent; other filters (environment, status) are kept.
    Otherwise the selectors are used as-is.
    """
    raw = dict(api_query_params or {})

    if cursor is not None:
        raw = {
            key: value
            for key, value in raw.items()
            if key not in DEPLOYMENT_TIMESTAMP_ORDER_BY
        }
        raw.pop("order_by", None)

    params = merge_updated_after_params(raw, cursor)
    return _with_timestamp_order_by(params)


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
