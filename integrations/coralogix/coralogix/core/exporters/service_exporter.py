import asyncio
from typing import Any, Optional

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from coralogix.clients.client import CoralogixClient
from coralogix.core.exporters.abstract_exporter import AbstractCoralogixExporter
from coralogix.core.options import ServiceOptions
from coralogix.helpers.exceptions import CoralogixMetricsQueryError
from coralogix.helpers.utils import (
    METRICS_API_PREFIX,
    SPAN_METRIC_NAMES,
    MetricsSource,
    SpanMetricNames,
    validate_label_filter,
)

QUERY_ENDPOINT = f"{METRICS_API_PREFIX}/query"
DEFAULT_WINDOW = "1h"
DEFAULT_LOOKBACK = "30d"
# Spans where a request enters a service: HTTP/gRPC servers and queue consumers.
ENTRY_SPAN_KINDS = 'span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"'
ERROR_STATUS = 'status_code="STATUS_CODE_ERROR"'
# Descriptive labels; any may be absent (compact span metrics keep only
# k8s_cluster_name, and non-Kubernetes services have no k8s_* labels).
_METADATA_LABELS = {
    "deployment_environment_name": "environments",
    "k8s_cluster_name": "clusters",
    "k8s_namespace_name": "namespaces",
}


def _promql_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
    return f'"{escaped}"'


def _selector(label_filter: str, *matchers: str) -> str:
    parts = [m for m in matchers if m]
    if label_filter:
        parts.append(label_filter)
    return "{" + ",".join(parts) + "}"


class ServiceExporter(AbstractCoralogixExporter[CoralogixClient]):
    """APM services from span metrics via the Metrics API (PromQL); the Service
    Catalog has no public list endpoint.

    A service is discovered if it emitted any span in `lookback`, so workers,
    batch jobs and idle services are included. Request rate, error rate and P95
    are measured on entry spans (server and consumer) over `window`."""

    async def _query(self, promql: str) -> list[dict[str, Any]]:
        response = await self.client.send_api_request(
            QUERY_ENDPOINT, params={"query": promql}
        )
        if response.get("status") != "success":
            detail = response.get("error") or "the metrics API returned no status"
            raise CoralogixMetricsQueryError(promql, str(detail))
        result = response.get("data", {}).get("result", [])
        if not isinstance(result, list):
            raise CoralogixMetricsQueryError(promql, "result was not a list")
        return result

    async def _resolve_metrics(
        self, source: MetricsSource, lookback: str, label_filter: str
    ) -> Optional[SpanMetricNames]:
        if source != MetricsSource.AUTO:
            return SPAN_METRIC_NAMES[source]
        for candidate, names in SPAN_METRIC_NAMES.items():
            if await self._query(
                f"count(count_over_time({names.calls}{_selector(label_filter)}[{lookback}]))"
            ):
                logger.info(
                    f"Using {candidate} span metrics ({names.calls}) for Coralogix services"
                )
                return names
        logger.warning(
            "No span metrics found in Coralogix (looked for "
            f"{', '.join(n.calls for n in SPAN_METRIC_NAMES.values())} in the last "
            f"{lookback}). Enable Span Metrics in the Coralogix OpenTelemetry "
            "integration, or set the service selector's metricsSource."
        )
        return None

    @staticmethod
    def _by_service(results: list[dict[str, Any]]) -> dict[str, float]:
        values: dict[str, float] = {}
        for result in results:
            name = result.get("metric", {}).get("service_name")
            value = (result.get("value") or [None, None])[1]
            if name and value not in (None, "NaN"):
                values[name] = float(value)
        return values

    async def _collect(
        self, options: ServiceOptions, service_name: Optional[str] = None
    ) -> list[RAW_ITEM]:
        window = options.get("window", DEFAULT_WINDOW)
        lookback = options.get("lookback", DEFAULT_LOOKBACK)
        label_filter = validate_label_filter(options.get("label_filter", ""))
        names = await self._resolve_metrics(
            options.get("metrics_source", MetricsSource.AUTO), lookback, label_filter
        )
        if names is None:
            return []

        scope = f"service_name={_promql_quote(service_name)}" if service_name else ""
        every_span = _selector(label_filter, scope)
        entry = _selector(label_filter, scope, ENTRY_SPAN_KINDS)
        entry_errors = _selector(label_filter, scope, ENTRY_SPAN_KINDS, ERROR_STATUS)
        group_labels = ", ".join(["service_name", *_METADATA_LABELS])

        discovered, total, failed, p95 = await asyncio.gather(
            self._query(
                f"count by ({group_labels}) "
                f"(max_over_time({names.calls}{every_span}[{lookback}]))"
            ),
            self._query(
                f"sum by (service_name) (rate({names.calls}{entry}[{window}]))"
            ),
            self._query(
                f"sum by (service_name) (rate({names.calls}{entry_errors}[{window}]))"
            ),
            self._query(
                "histogram_quantile(0.95, sum by (service_name, le) "
                f"(rate({names.duration}_bucket{entry}[{window}])))"
            ),
        )
        rps, error_rps, latency = (
            self._by_service(total),
            self._by_service(failed),
            self._by_service(p95),
        )

        services: dict[str, dict[str, set[str]]] = {}
        for result in discovered:
            metric = result.get("metric", {})
            name = metric.get("service_name")
            if not name:
                continue
            fields = services.setdefault(
                name, {field: set() for field in _METADATA_LABELS.values()}
            )
            for label, field in _METADATA_LABELS.items():
                if metric.get(label):
                    fields[field].add(metric[label])

        items: list[RAW_ITEM] = []
        for name in sorted(services):
            requests = rps.get(name, 0.0)
            items.append(
                {
                    "serviceName": name,
                    **{field: sorted(vals) for field, vals in services[name].items()},
                    "requestsPerSecond": requests,
                    "errorRatePct": (
                        100 * error_rps.get(name, 0.0) / requests if requests else None
                    ),
                    "p95LatencyMs": latency.get(name),
                    "window": window,
                    "metricsSource": names.calls,
                }
            )
        return items

    async def get_paginated_resources(
        self, options: ServiceOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        services = await self._collect(options)
        if services:
            yield self.with_team_url(services, await self.get_team_url())

    async def get_single_resource(
        self, resource_id: str, options: ServiceOptions | None = None
    ) -> Optional[RAW_ITEM]:
        query_options = options or ServiceOptions(
            window=DEFAULT_WINDOW,
            lookback=DEFAULT_LOOKBACK,
            metrics_source=MetricsSource.AUTO,
            label_filter="",
        )
        services = await self._collect(query_options, service_name=resource_id)
        return services[0] if services else None
