from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.helpers.async_client import OceanAsyncClient

from clients.auth.abstract_authenticator import AbstractAzureAuthenticator
from helpers.agent_observability_kql import build_agent_observability_query
from helpers.arm_scope import ensure_arm_deployment_scope
from helpers.project_scope import get_project_endpoint, project_name_from_endpoint


_LOG_ANALYTICS_SCOPE = "https://api.loganalytics.io/.default"
_MONITOR_METRICS_API = "2023-10-01"
_CHUNK_DAYS = 30

_AGENT_METRIC_NAMES = [
    "AgentInputTokens",
    "AgentOutputTokens",
    "AgentResponses",
    "AgentRuns",
    "AgentToolCalls",
    "AgentModelEstimatedCost",
]

_METRIC_TO_FIELD = {
    "AgentInputTokens": "metrics_input_tokens",
    "AgentOutputTokens": "metrics_output_tokens",
    "AgentResponses": "metrics_responses",
    "AgentRuns": "metrics_runs",
    "AgentToolCalls": "metrics_tool_calls",
    "AgentModelEstimatedCost": "metrics_estimated_cost_usd",
}


@dataclass(frozen=True)
class AgentObservabilityTotals:
    metrics_input_tokens: float = 0.0
    metrics_output_tokens: float = 0.0
    metrics_responses: float = 0.0
    metrics_runs: float = 0.0
    metrics_tool_calls: float = 0.0
    metrics_estimated_cost_usd: float = 0.0
    metrics_window_days: int = 30

    def to_agent_fields(self) -> dict[str, Any]:
        return {
            "metrics_input_tokens": int(self.metrics_input_tokens),
            "metrics_output_tokens": int(self.metrics_output_tokens),
            "metrics_responses": int(self.metrics_responses),
            "metrics_runs": int(self.metrics_runs),
            "metrics_tool_calls": int(self.metrics_tool_calls),
            "metrics_estimated_cost_usd": float(self.metrics_estimated_cost_usd),
            "metrics_window_days": self.metrics_window_days,
            "metrics_as_of": datetime.now(tz=UTC).isoformat(),
        }


class AgentObservabilityClient:
    def __init__(self, *, authenticator: AbstractAzureAuthenticator) -> None:
        self._authenticator = authenticator
        self._http = OceanAsyncClient(timeout=httpx.Timeout(120.0))

    async def close(self) -> None:
        await self._http.aclose()

    async def fetch_totals_by_agent_id(
        self, *, window_days: int
    ) -> dict[str, AgentObservabilityTotals]:
        window_days = max(1, min(window_days, 90))
        workspace_id = _config_value(
            "log_analytics_workspace_id", "logAnalyticsWorkspaceId"
        )
        if workspace_id:
            try:
                return await self._fetch_from_log_analytics(
                    workspace_id=workspace_id, window_days=window_days
                )
            except Exception as error:
                logger.warning(
                    f"Log Analytics agent metrics query failed, falling back to Monitor API: {error}"
                )
        return await self._fetch_from_monitor_metrics(window_days=window_days)

    async def _fetch_from_log_analytics(
        self, *, workspace_id: str, window_days: int
    ) -> dict[str, AgentObservabilityTotals]:
        query = build_agent_observability_query(window_days)
        headers = await self._log_analytics_headers()
        response = await self._http.post(
            f"https://api.loganalytics.io/v1/workspaces/{workspace_id}/query",
            headers={**headers, "Content-Type": "application/json"},
            json={"query": query},
        )
        response.raise_for_status()
        payload = response.json()
        return _parse_log_analytics_table(payload, window_days=window_days)

    async def _fetch_from_monitor_metrics(
        self, *, window_days: int
    ) -> dict[str, AgentObservabilityTotals]:
        scope = await ensure_arm_deployment_scope()
        project_name = project_name_from_endpoint(get_project_endpoint())
        resource_id = (
            f"/subscriptions/{scope.subscription_id}/resourceGroups/"
            f"{scope.resource_group_name}/providers/Microsoft.CognitiveServices/"
            f"accounts/{scope.account_name}/projects/{project_name}"
        )
        headers = await self._monitor_headers()
        end = datetime.now(tz=UTC)
        start = end - timedelta(days=window_days)

        totals: dict[str, AgentObservabilityTotals] = {}
        chunk_start = start
        while chunk_start < end:
            chunk_end = min(chunk_start + timedelta(days=_CHUNK_DAYS), end)
            timespan = (
                f"{chunk_start.strftime('%Y-%m-%dT%H:%M:%SZ')}/"
                f"{chunk_end.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            )
            url = (
                f"https://management.azure.com{resource_id}/providers/Microsoft.Insights/metrics"
            )
            response = await self._http.get(
                url,
                headers=headers,
                params={
                    "api-version": _MONITOR_METRICS_API,
                    "timespan": timespan,
                    "interval": "PT1H",
                    "metricnames": ",".join(_AGENT_METRIC_NAMES),
                    "aggregation": "Total",
                },
            )
            response.raise_for_status()
            _merge_monitor_payload(response.json(), totals, window_days=window_days)
            chunk_start = chunk_end

        return totals

    async def _log_analytics_headers(self) -> dict[str, str]:
        credential = getattr(self._authenticator, "_credential", None)
        if credential is None:
            return await self._authenticator.get_authorization_header()
        token = await credential.get_token(_LOG_ANALYTICS_SCOPE)
        return {"Authorization": f"Bearer {token.token}"}

    async def _monitor_headers(self) -> dict[str, str]:
        credential = getattr(self._authenticator, "_credential", None)
        if credential is None:
            return await self._authenticator.get_authorization_header()
        token = await credential.get_token("https://management.azure.com/.default")
        return {"Authorization": f"Bearer {token.token}"}


def _config_value(*keys: str) -> str | None:
    config: dict[str, Any] = ocean.integration_config
    for key in keys:
        value = config.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _parse_log_analytics_table(
    payload: dict[str, Any], *, window_days: int
) -> dict[str, AgentObservabilityTotals]:
    tables = payload.get("tables")
    if not isinstance(tables, list) or not tables:
        return {}

    table = tables[0]
    columns = table.get("columns") or []
    rows = table.get("rows") or []
    if not isinstance(columns, list) or not isinstance(rows, list):
        return {}

    names = [
        str(col.get("name"))
        for col in columns
        if isinstance(col, dict) and col.get("name")
    ]
    index = {name: idx for idx, name in enumerate(names)}
    agent_idx = index.get("AgentId")
    if agent_idx is None:
        return {}

    result: dict[str, AgentObservabilityTotals] = {}
    for row in rows:
        if not isinstance(row, list) or len(row) <= agent_idx:
            continue
        agent_id = str(row[agent_idx])
        if not agent_id:
            continue
        result[agent_id] = AgentObservabilityTotals(
            metrics_input_tokens=_cell_float(row, index, "metrics_input_tokens"),
            metrics_output_tokens=_cell_float(row, index, "metrics_output_tokens"),
            metrics_responses=_cell_float(row, index, "metrics_responses"),
            metrics_runs=_cell_float(row, index, "metrics_runs"),
            metrics_tool_calls=_cell_float(row, index, "metrics_tool_calls"),
            metrics_estimated_cost_usd=_cell_float(
                row, index, "metrics_estimated_cost_usd"
            ),
            metrics_window_days=window_days,
        )
    return result


def _cell_float(row: list[Any], index: dict[str, int], column: str) -> float:
    idx = index.get(column)
    if idx is None or idx >= len(row) or row[idx] is None:
        return 0.0
    return float(row[idx])


def _merge_monitor_payload(
    payload: dict[str, Any],
    totals: dict[str, AgentObservabilityTotals],
    *,
    window_days: int,
) -> None:
    values = payload.get("value")
    if not isinstance(values, list):
        return

    for metric_block in values:
        if not isinstance(metric_block, dict):
            continue
        metric_name = (metric_block.get("name") or {}).get("value")
        field = _METRIC_TO_FIELD.get(str(metric_name))
        if not field:
            continue
        timeseries = metric_block.get("timeseries")
        if not isinstance(timeseries, list):
            continue
        for series in timeseries:
            if not isinstance(series, dict):
                continue
            agent_id = _agent_id_from_metadata(series.get("metadatavalues"))
            if not agent_id:
                continue
            amount = _sum_series_total(series.get("data"))
            current = totals.get(agent_id) or AgentObservabilityTotals(
                metrics_window_days=window_days
            )
            updated = _add_to_totals(current, field, amount, window_days=window_days)
            totals[agent_id] = updated


def _agent_id_from_metadata(metadata_values: Any) -> str | None:
    if not isinstance(metadata_values, list):
        return None
    for item in metadata_values:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or {}).get("value")
        if name in {"AgentId", "agentId", "AgentName", "agentName"}:
            value = item.get("value")
            if value:
                return str(value)
    return None


def _sum_series_total(data: Any) -> float:
    if not isinstance(data, list):
        return 0.0
    total = 0.0
    for point in data:
        if isinstance(point, dict) and point.get("total") is not None:
            total += float(point["total"])
    return total


def _add_to_totals(
    current: AgentObservabilityTotals,
    field: str,
    amount: float,
    *,
    window_days: int,
) -> AgentObservabilityTotals:
    values = {
        "metrics_input_tokens": current.metrics_input_tokens,
        "metrics_output_tokens": current.metrics_output_tokens,
        "metrics_responses": current.metrics_responses,
        "metrics_runs": current.metrics_runs,
        "metrics_tool_calls": current.metrics_tool_calls,
        "metrics_estimated_cost_usd": current.metrics_estimated_cost_usd,
    }
    values[field] = values[field] + amount
    return AgentObservabilityTotals(
        metrics_window_days=window_days,
        **values,
    )


def enrich_agent_with_observability(
    agent: dict[str, object],
    metrics_by_agent_id: dict[str, AgentObservabilityTotals],
) -> dict[str, object]:
    if not metrics_by_agent_id:
        return agent
    agent_id = str(agent.get("id") or agent.get("name") or "")
    if not agent_id:
        return agent
    totals = metrics_by_agent_id.get(agent_id)
    if totals is None:
        for key, value in metrics_by_agent_id.items():
            if key.lower() == agent_id.lower():
                totals = value
                break
    if totals is None:
        return agent
    merged = dict(agent)
    merged.update(totals.to_agent_fields())
    return merged
