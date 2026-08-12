"""Incremental sync strategy constants and helpers for Azure DevOps."""

from datetime import datetime, timezone
from typing import Any

from port_ocean.core.incremental.strategies import ServerSideTimestampStrategy

ANALYTICS_PIPELINE_RUNS_ODATA_PATH = "/_odata/v4.0-preview/PipelineRuns"
ANALYTICS_PIPELINE_RUNS_PAGE_SIZE = 100

BUILD_INCREMENTAL = ServerSideTimestampStrategy(param_key="minTime")
RELEASE_INCREMENTAL = ServerSideTimestampStrategy(param_key="minCreatedTime")
RELEASE_DEPLOYMENT_INCREMENTAL = ServerSideTimestampStrategy(
    param_key="minModifiedTime"
)
ADVANCED_SECURITY_INCREMENTAL = ServerSideTimestampStrategy(
    param_key="criteria.modifiedSince"
)


def wiql_changed_after_clause(cursor: datetime, *, time_precision: bool = False) -> str:
    """Build a WIQL fragment filtering work items changed on or after *cursor*.

    When *time_precision* is False, only the UTC calendar date is used (ADO default
    date-precision WIQL). When True, a full UTC ISO timestamp is used and the WIQL
    request must include ``timePrecision=true``.
    """
    if time_precision:
        cursor_value = cursor.astimezone(timezone.utc).isoformat()
    else:
        cursor_value = cursor.astimezone(timezone.utc).date().isoformat()
    return f"[System.ChangedDate] >= '{cursor_value}'"


def flatten_advanced_security_params(params: dict[str, Any]) -> dict[str, Any]:
    """Flatten nested ``criteria`` dict to ADO query keys like ``criteria.modifiedSince``."""
    flattened: dict[str, Any] = {}
    for key, value in params.items():
        if key == "criteria" and isinstance(value, dict):
            for criteria_key, criteria_value in value.items():
                if criteria_value is not None:
                    flattened[f"criteria.{criteria_key}"] = criteria_value
        elif value is not None:
            flattened[key] = value
    return flattened


def build_pipeline_runs_analytics_filter(cursor: datetime) -> str:
    """Build an OData ``$filter`` for Analytics ``PipelineRuns`` incremental discovery."""
    return f"CompletedDate ge {cursor.isoformat()}"
