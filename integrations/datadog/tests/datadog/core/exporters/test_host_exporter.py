from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, call, patch

import pytest

from datadog.client import DatadogClient
from datadog.core.exporters import HostExporter
from datadog.core.exporters.base_exporter import MAX_PAGE_SIZE
from datadog.core.exporters.host_exporter import HOST_EDITS_AUDIT_QUERY

CURSOR = datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc)
EMPTY_HOSTS: dict[str, list[dict[str, Any]]] = {"host_list": []}
NO_AUDIT_EVENTS: dict[str, list[dict[str, Any]]] = {"data": []}
HOST_EDIT_EVENT = {
    "data": [
        {
            "id": "event-1",
            "attributes": {
                "attributes": {
                    "http": {
                        "method": "POST",
                        "url_details": {"path": "/source/update_tags"},
                    }
                }
            },
        }
    ]
}


async def _collect(
    exporter: HostExporter, incremental_cursor: datetime | None = None
) -> list[dict[str, Any]]:
    hosts: list[dict[str, Any]] = []
    async for batch in exporter.get_paginated_resources(
        incremental_cursor=incremental_cursor
    ):
        hosts.extend(batch)
    return hosts


def _hosts_url(client: DatadogClient) -> str:
    return f"{client.api_url}/api/v1/hosts"


def _audit_call(client: DatadogClient) -> Any:
    return call(
        f"{client.api_url}/api/v2/audit/events/search",
        json_data={
            "filter": {
                "query": HOST_EDITS_AUDIT_QUERY,
                "from": CURSOR.isoformat(),
                "to": "now",
            },
            "sort": "-timestamp",
            "page": {"limit": 1},
        },
        method="POST",
    )


def test_host_edits_query_matches_tag_and_mute_writes() -> None:
    assert "*update_tags*" in HOST_EDITS_AUDIT_QUERY
    assert "*tags/hosts*" in HOST_EDITS_AUDIT_QUERY
    assert "*mute*" in HOST_EDITS_AUDIT_QUERY
    assert "-@http.method:GET" in HOST_EDITS_AUDIT_QUERY


@pytest.mark.asyncio
async def test_get_hosts_without_cursor_lists_every_host(
    mock_datadog_client: DatadogClient,
) -> None:
    first_page = {"host_list": [{"id": 1}, {"id": 2}]}
    second_page = {"host_list": [{"id": 3}]}
    url = _hosts_url(mock_datadog_client)

    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [first_page, second_page, EMPTY_HOSTS]

        hosts = await _collect(HostExporter(mock_datadog_client))

    assert hosts == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert mock_request.call_args_list == [
        call(url, params={"start": 0, "count": MAX_PAGE_SIZE}),
        call(url, params={"start": MAX_PAGE_SIZE, "count": MAX_PAGE_SIZE}),
        call(url, params={"start": 2 * MAX_PAGE_SIZE, "count": MAX_PAGE_SIZE}),
    ]


@pytest.mark.asyncio
async def test_get_hosts_with_cursor_and_no_edits_lists_hosts_reported_since(
    mock_datadog_client: DatadogClient,
) -> None:
    first_page = {"host_list": [{"id": 1, "up": True}, {"id": 2, "up": False}]}
    url = _hosts_url(mock_datadog_client)
    expected_from = int(CURSOR.timestamp())

    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [NO_AUDIT_EVENTS, first_page, EMPTY_HOSTS]

        hosts = await _collect(
            HostExporter(mock_datadog_client), incremental_cursor=CURSOR
        )

    assert hosts == first_page["host_list"]
    assert mock_request.call_args_list == [
        _audit_call(mock_datadog_client),
        call(url, params={"start": 0, "count": MAX_PAGE_SIZE, "from": expected_from}),
        call(
            url,
            params={
                "start": MAX_PAGE_SIZE,
                "count": MAX_PAGE_SIZE,
                "from": expected_from,
            },
        ),
    ]


@pytest.mark.asyncio
async def test_get_hosts_with_cursor_and_host_edits_lists_every_host(
    mock_datadog_client: DatadogClient,
) -> None:
    page = {"host_list": [{"id": 1, "up": True}, {"id": 2, "up": False}]}
    url = _hosts_url(mock_datadog_client)

    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [HOST_EDIT_EVENT, page, EMPTY_HOSTS]

        hosts = await _collect(
            HostExporter(mock_datadog_client), incremental_cursor=CURSOR
        )

    assert hosts == page["host_list"]
    assert mock_request.call_args_list == [
        _audit_call(mock_datadog_client),
        call(url, params={"start": 0, "count": MAX_PAGE_SIZE}),
        call(url, params={"start": MAX_PAGE_SIZE, "count": MAX_PAGE_SIZE}),
    ]
