from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from datadog.client import DatadogClient
from datadog.core.exporters import ServiceExporter
from datadog.core.exporters.base_exporter import MAX_PAGE_SIZE
from datadog.incremental import CHANGED_SERVICES_AUDIT_QUERY

API_URL = "https://api.datadoghq.com"
SINCE = datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc)


def _audit_event(ref: str) -> dict[str, Any]:
    # Shaped after a real event: the asset ID is the catalog entity reference
    return {
        "id": f"event-{ref}",
        "attributes": {"attributes": {"asset": {"id": ref, "type": "idp_entity"}}},
    }


def _audit_page(*events: dict[str, Any], after: str | None = None) -> dict[str, Any]:
    return {"data": list(events), "meta": {"page": {"after": after} if after else {}}}


def _service(name: str) -> dict[str, Any]:
    return {
        "id": f"id-{name}",
        "type": "service-definition",
        "attributes": {"schema": {"schema-version": "v2.2", "dd-service": name}},
    }


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", f"{API_URL}/api/v2/services/definitions/x")
    return httpx.HTTPStatusError(
        "error", request=request, response=httpx.Response(status, request=request)
    )


async def _collect_changed(exporter: ServiceExporter) -> list[dict[str, Any]]:
    services: list[dict[str, Any]] = []
    async for batch in exporter.get_changed_services(incremental_cursor=SINCE):
        services.extend(batch)
    return services


@pytest.mark.asyncio
async def test_get_changed_services_searches_audit_events_since_cursor(
    mock_datadog_client: DatadogClient,
) -> None:
    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = _audit_page()

        assert await _collect_changed(ServiceExporter(mock_datadog_client)) == []

        mock_request.assert_called_once_with(
            f"{API_URL}/api/v2/audit/events/search",
            json_data={
                "filter": {
                    "query": CHANGED_SERVICES_AUDIT_QUERY,
                    "from": "2026-11-05T10:00:00+00:00",
                    "to": "now",
                },
                "sort": "-timestamp",
                "page": {"limit": MAX_PAGE_SIZE},
            },
            method="POST",
        )


@pytest.mark.asyncio
async def test_get_changed_services_fetches_each_service_once_by_name(
    mock_datadog_client: DatadogClient,
) -> None:
    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            _audit_page(
                _audit_event("service:default/checkout"),
                _audit_event("service:default/checkout"),
                after="next",
            ),
            _audit_page(_audit_event("service:default/payments")),
            {"data": _service("checkout")},
            {"data": _service("payments")},
        ]

        services = await _collect_changed(ServiceExporter(mock_datadog_client))

        assert services == [_service("checkout"), _service("payments")]
        assert mock_request.call_args_list[1].kwargs["json_data"]["page"] == {
            "limit": MAX_PAGE_SIZE,
            "cursor": "next",
        }
        # Same schema version as the full resync, so services keep one shape
        mock_request.assert_any_call(
            f"{API_URL}/api/v2/services/definitions/checkout",
            params={"schema_version": "v2.2"},
        )
        mock_request.assert_any_call(
            f"{API_URL}/api/v2/services/definitions/payments",
            params={"schema_version": "v2.2"},
        )


@pytest.mark.asyncio
async def test_get_changed_services_skips_services_that_no_longer_exist(
    mock_datadog_client: DatadogClient,
) -> None:
    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            _audit_page(
                _audit_event("service:default/gone"),
                _audit_event("service:default/payments"),
            ),
            _http_error(404),
            {"data": _service("payments")},
        ]

        services = await _collect_changed(ServiceExporter(mock_datadog_client))

        assert services == [_service("payments")]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 500])
async def test_get_changed_services_raises_other_fetch_errors(
    mock_datadog_client: DatadogClient, status: int
) -> None:
    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            _audit_page(_audit_event("service:default/checkout")),
            _http_error(status),
        ]

        with pytest.raises(httpx.HTTPStatusError):
            await _collect_changed(ServiceExporter(mock_datadog_client))
