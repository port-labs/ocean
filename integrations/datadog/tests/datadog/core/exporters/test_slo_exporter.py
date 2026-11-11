from datetime import datetime, timezone
from typing import Any, Iterator
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from datadog.client import DatadogClient
from datadog.core.exporters.base_exporter import MAX_PAGE_SIZE
from datadog.core.exporters.slo_exporter import (
    CHANGED_RESTRICTION_POLICIES_AUDIT_QUERY,
    CHANGED_SLOS_AUDIT_QUERY,
    GetSloOptions,
    ListSloOptions,
    SloExporter,
)

AUDIT_SEARCH_URL = "https://api.datadoghq.com/api/v2/audit/events/search"
SINCE = datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc)


def _audit_event(asset_id: str) -> dict[str, Any]:
    return {
        "id": f"event-{asset_id}",
        "attributes": {"attributes": {"asset": {"id": asset_id}}},
    }


def _audit_page(*events: dict[str, Any], after: str | None = None) -> dict[str, Any]:
    return {"data": list(events), "meta": {"page": {"after": after} if after else {}}}


def _slo(slo_id: str) -> dict[str, Any]:
    return {"id": slo_id, "name": f"slo-{slo_id}"}


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://api.datadoghq.com/api/v1/slo/1")
    return httpx.HTTPStatusError(
        "error", request=request, response=httpx.Response(status, request=request)
    )


async def _collect(
    exporter: SloExporter, options: ListSloOptions = ListSloOptions()
) -> list[dict[str, Any]]:
    slos: list[dict[str, Any]] = []
    async for batch in exporter.get_changed_slos(options, since=SINCE):
        slos.extend(batch)
    return slos


def _searched_query(mock_request: AsyncMock, call_index: int) -> str:
    return mock_request.call_args_list[call_index].kwargs["json_data"]["filter"][
        "query"
    ]


@pytest.fixture
def audit_mocks(
    mock_datadog_client: DatadogClient,
) -> Iterator[tuple[AsyncMock, AsyncMock]]:
    """Patch the audit search request and the per-SLO fetch.

    By default every fetched SLO exists.
    """
    with (
        patch.object(
            mock_datadog_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request,
        patch.object(
            SloExporter, "get_resource", new_callable=AsyncMock
        ) as mock_get_resource,
    ):
        mock_get_resource.side_effect = lambda options: _slo(options.resource_id)
        yield mock_request, mock_get_resource


def test_changed_slos_query_matches_created_or_modified_slos() -> None:
    assert CHANGED_SLOS_AUDIT_QUERY == (
        "@evt.name:SLO @asset.type:slo @action:(created OR modified)"
    )


def test_changed_restriction_policies_query_matches_modified_or_deleted() -> None:
    assert CHANGED_RESTRICTION_POLICIES_AUDIT_QUERY == (
        '@evt.name:"Access Management" @asset.type:restriction_policy '
        "@action:(modified OR deleted)"
    )


@pytest.mark.asyncio
async def test_get_changed_slos_searches_audit_events_since_cursor(
    mock_datadog_client: DatadogClient,
    audit_mocks: tuple[AsyncMock, AsyncMock],
) -> None:
    mock_request, _ = audit_mocks
    mock_request.return_value = _audit_page()

    await _collect(SloExporter(mock_datadog_client))

    mock_request.assert_called_once_with(
        AUDIT_SEARCH_URL,
        json_data={
            "filter": {
                "query": CHANGED_SLOS_AUDIT_QUERY,
                "from": "2026-11-05T10:00:00+00:00",
                "to": "now",
            },
            "sort": "-timestamp",
            "page": {"limit": MAX_PAGE_SIZE},
        },
        method="POST",
    )


@pytest.mark.asyncio
async def test_get_changed_slos_follows_cursor_and_dedupes(
    mock_datadog_client: DatadogClient,
    audit_mocks: tuple[AsyncMock, AsyncMock],
) -> None:
    mock_request, mock_get_resource = audit_mocks
    mock_request.side_effect = [
        _audit_page(_audit_event("1"), _audit_event("2"), after="next"),
        _audit_page(_audit_event("2"), _audit_event("3")),
    ]

    slos = await _collect(SloExporter(mock_datadog_client))

    assert slos == [_slo("1"), _slo("2"), _slo("3")]
    assert mock_get_resource.await_count == 3
    second_body = mock_request.call_args_list[1].kwargs["json_data"]
    assert second_body["page"] == {"limit": MAX_PAGE_SIZE, "cursor": "next"}


@pytest.mark.asyncio
async def test_get_changed_slos_includes_slo_restriction_policy_changes(
    mock_datadog_client: DatadogClient,
    audit_mocks: tuple[AsyncMock, AsyncMock],
) -> None:
    mock_request, mock_get_resource = audit_mocks
    mock_request.side_effect = [
        _audit_page(_audit_event("1")),
        # Policies of other asset types and malformed ids are ignored
        _audit_page(
            _audit_event("slo:1"),
            _audit_event("slo:2"),
            _audit_event("monitor:3"),
            _audit_event("malformed"),
        ),
    ]

    slos = await _collect(
        SloExporter(mock_datadog_client),
        ListSloOptions(include_restriction_policy=True),
    )

    assert slos == [_slo("1"), _slo("2")]
    assert _searched_query(mock_request, 0) == CHANGED_SLOS_AUDIT_QUERY
    assert _searched_query(mock_request, 1) == CHANGED_RESTRICTION_POLICIES_AUDIT_QUERY
    mock_get_resource.assert_any_await(
        GetSloOptions(resource_id="2", include_restriction_policy=True)
    )


@pytest.mark.asyncio
async def test_get_changed_slos_skips_restriction_policy_search_when_disabled(
    mock_datadog_client: DatadogClient,
    audit_mocks: tuple[AsyncMock, AsyncMock],
) -> None:
    mock_request, mock_get_resource = audit_mocks
    mock_request.return_value = _audit_page(_audit_event("1"))

    slos = await _collect(SloExporter(mock_datadog_client))

    assert slos == [_slo("1")]
    assert mock_request.call_count == 1
    mock_get_resource.assert_awaited_once_with(
        GetSloOptions(resource_id="1", include_restriction_policy=False)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [404, 500])
async def test_get_changed_slos_skips_slos_that_fail_to_fetch(
    mock_datadog_client: DatadogClient,
    audit_mocks: tuple[AsyncMock, AsyncMock],
    status: int,
) -> None:
    mock_request, mock_get_resource = audit_mocks
    mock_request.return_value = _audit_page(_audit_event("1"), _audit_event("2"))
    mock_get_resource.side_effect = [_http_error(status), _slo("2")]

    slos = await _collect(SloExporter(mock_datadog_client))

    assert slos == [_slo("2")]
