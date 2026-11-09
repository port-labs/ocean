"""Query-param builders for incremental resyncs.

Each ``build_incremental_*_params`` builds the query for a run that has a cursor:
it drops the selector's ``TIMESTAMP_SELECTORS`` and applies the cursor filter.
The matching full-resync builders live in ``gitlab/clients/utils.py``. Resync
handlers in ``main.py`` pick one or the other on ``sync_cursor``.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from port_ocean.core.incremental.strategies import ServerSideTimestampStrategy

from gitlab.clients.options import IssueOptions
from gitlab.clients.utils import (
    MergeRequestState,
    build_project_params,
)

# GitLab filters list endpoints server-side by the resource's updated_at.
UPDATED_AFTER_INCREMENTAL = ServerSideTimestampStrategy(param_key="updated_after")
LAST_ACTIVITY_AFTER_INCREMENTAL = ServerSideTimestampStrategy(
    param_key="last_activity_after"
)

# Selector time filters dropped by every incremental builder; the cursor replaces them.
TIMESTAMP_SELECTORS = {
    "finished_after",
    "finished_before",
    "updated_after",
    "updated_before",
}


def _drop_timestamp_selectors(
    selector_params: Mapping[str, Any] | None,
    *extra_keys: str,
) -> dict[str, Any]:
    """Return the non-None selector filters minus ``TIMESTAMP_SELECTORS`` and *extra_keys*."""
    dropped = TIMESTAMP_SELECTORS.union(extra_keys)
    return {
        key: value
        for key, value in (selector_params or {}).items()
        if key not in dropped and value is not None
    }


def build_incremental_projects_params(
    include_only_active_projects: bool | None,
    cursor: datetime,
) -> dict[str, Any]:
    """Query params for ``GET /projects`` on an incremental run (``last_activity_after``)."""
    params = _drop_timestamp_selectors(
        build_project_params(include_only_active_projects=include_only_active_projects)
    )
    return LAST_ACTIVITY_AFTER_INCREMENTAL.merge_params(params, cursor)


def build_incremental_project_updated_params(
    include_only_active_projects: bool | None,
    cursor: datetime,
) -> dict[str, Any]:
    """Query params for ``GET /projects`` on an incremental run (``updated_after``).

    Used by the file, folder, skill and plugin resyncs.
    """
    params = _drop_timestamp_selectors(
        build_project_params(include_only_active_projects=include_only_active_projects),
        "order_by",
    )
    params = UPDATED_AFTER_INCREMENTAL.merge_params(params, cursor)
    params["order_by"] = "updated_at"
    return params


def build_incremental_issue_params(
    options: IssueOptions,
    cursor: datetime,
) -> dict[str, Any]:
    """Query params for ``GET /groups/{id}/issues`` on an incremental run."""
    return UPDATED_AFTER_INCREMENTAL.merge_params(
        _drop_timestamp_selectors(options), cursor
    )


def build_incremental_merge_request_params(
    state: MergeRequestState,
    cursor: datetime,
) -> dict[str, Any]:
    """Query params for ``GET /groups/{id}/merge_requests`` on an incremental run."""
    return UPDATED_AFTER_INCREMENTAL.merge_params(
        _drop_timestamp_selectors({"state": state}), cursor
    )


def build_incremental_pipeline_params(
    api_query_params: dict[str, Any] | None,
    cursor: datetime,
) -> dict[str, Any]:
    """Query params for ``GET /projects/{id}/pipelines`` on an incremental run."""
    return UPDATED_AFTER_INCREMENTAL.merge_params(
        _drop_timestamp_selectors(api_query_params), cursor
    )


def build_incremental_deployment_params(
    selector_params: dict[str, Any] | None,
    cursor: datetime,
) -> dict[str, Any]:
    """Query params for ``GET /projects/{id}/deployments`` on an incremental run.

    The selector ``order_by`` is dropped too and replaced by ``order_by=updated_at``.
    """
    params = _drop_timestamp_selectors(selector_params, "order_by")
    params = UPDATED_AFTER_INCREMENTAL.merge_params(params, cursor)
    params["order_by"] = "updated_at"
    return params
