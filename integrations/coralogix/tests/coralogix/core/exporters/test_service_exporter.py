from typing import Any

import pytest

from coralogix.core.exporters.service_exporter import ServiceExporter
from coralogix.core.options import ServiceOptions
from coralogix.helpers.exceptions import CoralogixApiError, CoralogixMetricsQueryError
from coralogix.helpers.utils import MetricsSource
from tests.conftest import TEAM_URL
from tests.coralogix.core.exporters.helpers import collect, mock_client


def _vector(*rows: tuple[dict[str, str], str]) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {"result": [{"metric": m, "value": [1700000000, v]} for m, v in rows]},
    }


def _metrics(available: tuple[str, ...] = ("calls_total",)) -> Any:
    """Fake Metrics API: only queries on a metric in `available` (or its
    duration histogram) return data."""
    prefixes = tuple(name.removesuffix("calls_total") for name in available)

    def respond(kwargs: dict[str, Any]) -> dict[str, Any]:
        query = kwargs["params"]["query"]
        if not any(
            f"{p}calls_total{{" in query or f"{p}duration" in query for p in prefixes
        ):
            return _vector()
        if query.startswith("count(count_over_time"):
            return _vector(({}, "42"))
        if query.startswith("count by"):
            return _vector(
                (
                    {
                        "service_name": "payment-service",
                        "k8s_namespace_name": "payments",
                        "k8s_cluster_name": "eu-prod",
                        "deployment_environment_name": "prod",
                    },
                    "1",
                ),
                (
                    {
                        "service_name": "payment-service",
                        "k8s_cluster_name": "eu-staging",
                        "deployment_environment_name": "staging",
                    },
                    "1",
                ),
                ({"service_name": "order-worker"}, "1"),
            )
        if query.startswith("histogram_quantile"):
            return _vector(({"service_name": "payment-service"}, "195.5"))
        if "STATUS_CODE_ERROR" in query:
            return _vector(({"service_name": "payment-service"}, "0.05"))
        return _vector(({"service_name": "payment-service"}, "1.0"))

    return respond


def _queries(client: Any) -> list[str]:
    return [
        call.kwargs["params"]["query"]
        for call in client.send_api_request.call_args_list
        if "params" in call.kwargs
    ]


async def test_discovers_every_service_and_merges_environments() -> None:
    client = mock_client({"metrics/api/v1/query": _metrics()})
    services = await collect(
        ServiceExporter(client).get_paginated_resources(ServiceOptions(window="1h"))
    )
    by_name = {s["serviceName"]: s for s in services}
    assert set(by_name) == {"order-worker", "payment-service"}

    payment = by_name["payment-service"]
    assert payment["environments"] == ["prod", "staging"]
    assert payment["clusters"] == ["eu-prod", "eu-staging"]
    assert payment["namespaces"] == ["payments"]
    assert payment["requestsPerSecond"] == 1.0
    assert payment["errorRatePct"] == pytest.approx(5.0)
    assert payment["p95LatencyMs"] == 195.5
    assert payment["metricsSource"] == "calls_total"
    assert payment["__teamUrl"] == TEAM_URL


async def test_service_without_entry_traffic_is_still_synced() -> None:
    client = mock_client({"metrics/api/v1/query": _metrics()})
    services = await collect(
        ServiceExporter(client).get_paginated_resources(ServiceOptions(window="1h"))
    )
    worker = next(s for s in services if s["serviceName"] == "order-worker")
    assert worker["requestsPerSecond"] == 0.0
    assert worker["errorRatePct"] is None
    assert worker["p95LatencyMs"] is None
    assert worker["environments"] == [] and worker["namespaces"] == []


async def test_discovery_uses_all_spans_and_red_uses_entry_spans() -> None:
    client = mock_client({"metrics/api/v1/query": _metrics()})
    await collect(
        ServiceExporter(client).get_paginated_resources(
            ServiceOptions(window="15m", lookback="30d")
        )
    )
    queries = _queries(client)
    discovery = next(q for q in queries if q.startswith("count by"))
    assert "[30d]" in discovery and "span_kind" not in discovery
    red = [q for q in queries if q.startswith(("sum by", "histogram_quantile"))]
    assert len(red) == 3
    assert all("SPAN_KIND_SERVER|SPAN_KIND_CONSUMER" in q and "[15m]" in q for q in red)


async def test_auto_detects_compact_span_metrics() -> None:
    client = mock_client(
        {"metrics/api/v1/query": _metrics(available=("compact_calls_total",))}
    )
    services = await collect(
        ServiceExporter(client).get_paginated_resources(ServiceOptions(window="1h"))
    )
    assert services and services[0]["metricsSource"] == "compact_calls_total"
    assert any("compact_duration_ms_bucket" in q for q in _queries(client))


async def test_explicit_metrics_source_skips_detection() -> None:
    client = mock_client(
        {
            "metrics/api/v1/query": _metrics(
                available=("traces_span_metrics_calls_total",)
            )
        }
    )
    services = await collect(
        ServiceExporter(client).get_paginated_resources(
            ServiceOptions(
                window="1h", metrics_source=MetricsSource.OTEL_SPANMETRICS_CONNECTOR
            )
        )
    )
    queries = _queries(client)
    assert services
    assert not any(q.startswith("count(count_over_time") for q in queries)
    assert any("traces_span_metrics_duration_milliseconds_bucket" in q for q in queries)


async def test_no_span_metrics_yields_nothing() -> None:
    client = mock_client({"metrics/api/v1/query": _metrics(available=())})
    assert (
        await collect(
            ServiceExporter(client).get_paginated_resources(ServiceOptions(window="1h"))
        )
        == []
    )


async def test_label_filter_reaches_every_query() -> None:
    client = mock_client({"metrics/api/v1/query": _metrics()})
    await collect(
        ServiceExporter(client).get_paginated_resources(
            ServiceOptions(window="1h", label_filter='k8s_cluster_name="eu-prod"')
        )
    )
    assert all('k8s_cluster_name="eu-prod"' in q for q in _queries(client))


async def test_failed_metrics_query_fails_the_sync() -> None:
    client = mock_client(
        {"metrics/api/v1/query": {"status": "error", "error": "bad query"}}
    )
    with pytest.raises(CoralogixMetricsQueryError):
        await collect(
            ServiceExporter(client).get_paginated_resources(ServiceOptions(window="1h"))
        )


async def test_missing_team_url_fails_the_sync() -> None:
    client = mock_client(
        {
            "aaa/identity/v1/whoami": {},
            "metrics/api/v1/query": _metrics(),
        }
    )
    with pytest.raises(CoralogixApiError, match="team URL"):
        await collect(
            ServiceExporter(client).get_paginated_resources(ServiceOptions(window="1h"))
        )


async def test_get_single_resource_scopes_to_service() -> None:
    client = mock_client({"metrics/api/v1/query": _metrics()})
    service = await ServiceExporter(client).get_single_resource("payment-service")
    assert service is not None
    queries = _queries(client)
    discovery = next(q for q in queries if q.startswith("count by"))
    assert "[30d]" in discovery
    scoped = [q for q in queries if not q.startswith("count(count_over_time")]
    assert all('service_name="payment-service"' in q for q in scoped)


async def test_get_single_resource_honors_options() -> None:
    client = mock_client({"metrics/api/v1/query": _metrics()})
    await ServiceExporter(client).get_single_resource(
        "payment-service",
        ServiceOptions(
            window="15m",
            lookback="7d",
            metrics_source=MetricsSource.SPAN_METRICS,
            label_filter='k8s_cluster_name="prod"',
        ),
    )
    queries = _queries(client)
    assert not any(q.startswith("count(count_over_time") for q in queries)
    assert any("[7d]" in q and "[15m]" not in q for q in queries)
    assert all('k8s_cluster_name="prod"' in q for q in queries)


async def test_service_name_is_escaped_in_promql() -> None:
    client = mock_client({"metrics/api/v1/query": _metrics()})
    await ServiceExporter(client).get_single_resource('pay"ment')
    scoped = [q for q in _queries(client) if not q.startswith("count(count_over_time")]
    assert all(r'service_name="pay\"ment"' in q for q in scoped)
