from datetime import datetime, timezone
from typing import Any, Iterator
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from datadog.client import DatadogClient
from datadog.core.exporters.base_exporter import (
    CHANGED_RESOURCES_FETCH_BATCH_SIZE,
    MAX_PAGE_SIZE,
)
from datadog.core.exporters import TeamExporter
from datadog.core.exporters.team_exporter import (
    GetTeamOptions,
    ListTeamOptions,
)
from datadog.incremental import CHANGED_TEAMS_AUDIT_QUERY


@pytest.mark.asyncio
async def test_get_teams(mock_datadog_client: DatadogClient) -> None:
    teams_response: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "1", "type": "team"}, {"id": "2", "type": "team"}]
    }
    empty_response: dict[str, list[dict[str, Any]]] = {"data": []}

    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [teams_response, empty_response]

        exporter = TeamExporter(mock_datadog_client)
        teams = []
        async for team_batch in exporter.get_paginated_resources(ListTeamOptions()):
            teams.extend(team_batch)

        assert len(teams) == 2
        assert teams == teams_response["data"]
        mock_request.assert_any_call(
            f"{mock_datadog_client.api_url}/api/v2/team",
            params={"page[size]": MAX_PAGE_SIZE, "page[number]": 0},
        )


@pytest.mark.asyncio
async def test_get_teams_multiple_pages(mock_datadog_client: DatadogClient) -> None:
    first_page: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "1", "type": "team"}]
    }
    second_page: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "2", "type": "team"}]
    }
    third_page: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "3", "type": "team"}]
    }
    empty_page: dict[str, list[dict[str, Any]]] = {"data": []}

    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [first_page, second_page, third_page, empty_page]

        exporter = TeamExporter(mock_datadog_client)
        teams = []
        async for team_batch in exporter.get_paginated_resources(ListTeamOptions()):
            teams.extend(team_batch)

        assert len(teams) == 3
        assert teams == first_page["data"] + second_page["data"] + third_page["data"]
        assert mock_request.call_count == 4


@pytest.mark.asyncio
async def test_get_teams_with_members(mock_datadog_client: DatadogClient) -> None:
    teams_response: dict[str, list[dict[str, Any]]] = {
        "data": [{"id": "team1", "type": "team"}]
    }
    empty_teams: dict[str, list[dict[str, Any]]] = {"data": []}
    members_response: dict[str, list[dict[str, Any]]] = {
        "included": [{"id": "1", "type": "users"}, {"id": "2", "type": "users"}]
    }
    empty_members: dict[str, list[dict[str, Any]]] = {"included": []}

    with patch.object(
        mock_datadog_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            teams_response,
            members_response,
            empty_members,
            empty_teams,
        ]

        exporter = TeamExporter(mock_datadog_client)
        teams = []
        async for team_batch in exporter.get_paginated_resources(
            ListTeamOptions(include_members=True)
        ):
            teams.extend(team_batch)

        assert len(teams) == 1
        assert teams[0]["__members"] == members_response["included"]


AUDIT_SEARCH_URL = "https://api.datadoghq.com/api/v2/audit/events/search"
SINCE = datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc)


def _audit_event(team_id: str) -> dict[str, Any]:
    return {
        "id": f"event-{team_id}",
        "attributes": {"attributes": {"asset": {"id": team_id}}},
    }


def _audit_page(*events: dict[str, Any], after: str | None = None) -> dict[str, Any]:
    return {"data": list(events), "meta": {"page": {"after": after} if after else {}}}


def _team(team_id: str) -> dict[str, Any]:
    return {"id": team_id, "type": "team"}


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://api.datadoghq.com/api/v2/team/1")
    return httpx.HTTPStatusError(
        "error", request=request, response=httpx.Response(status, request=request)
    )


async def _collect_changed(
    exporter: TeamExporter, options: ListTeamOptions = ListTeamOptions()
) -> list[dict[str, Any]]:
    teams: list[dict[str, Any]] = []
    async for batch in exporter.get_changed_teams(options, incremental_cursor=SINCE):
        teams.extend(batch)
    return teams


@pytest.fixture
def team_audit_mocks(
    mock_datadog_client: DatadogClient,
) -> Iterator[tuple[AsyncMock, AsyncMock]]:
    """Patch the audit search request and the per-team fetch.

    By default every fetched team exists.
    """
    with (
        patch.object(
            mock_datadog_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request,
        patch.object(
            TeamExporter, "get_resource", new_callable=AsyncMock
        ) as mock_get_resource,
    ):
        mock_get_resource.side_effect = lambda options: _team(options.resource_id)
        yield mock_request, mock_get_resource


def test_changed_teams_query_includes_membership_removals_but_not_team_deletions() -> (
    None
):
    assert CHANGED_TEAMS_AUDIT_QUERY == (
        '@evt.name:"Teams Management" '
        "(@action:(created OR modified) OR (@action:deleted @asset.name:membership-*))"
    )


@pytest.mark.asyncio
async def test_get_changed_teams_searches_audit_events_since_cursor(
    mock_datadog_client: DatadogClient,
    team_audit_mocks: tuple[AsyncMock, AsyncMock],
) -> None:
    mock_request, _ = team_audit_mocks
    mock_request.return_value = _audit_page()

    assert await _collect_changed(TeamExporter(mock_datadog_client)) == []

    mock_request.assert_called_once_with(
        AUDIT_SEARCH_URL,
        json_data={
            "filter": {
                "query": CHANGED_TEAMS_AUDIT_QUERY,
                "from": "2026-11-05T10:00:00+00:00",
                "to": "now",
            },
            "sort": "-timestamp",
            "page": {"limit": MAX_PAGE_SIZE},
        },
        method="POST",
    )


@pytest.mark.asyncio
async def test_get_changed_teams_follows_cursor_and_dedupes(
    mock_datadog_client: DatadogClient,
    team_audit_mocks: tuple[AsyncMock, AsyncMock],
) -> None:
    mock_request, mock_get_resource = team_audit_mocks
    # Several membership events for one team yield a single fetch
    mock_request.side_effect = [
        _audit_page(_audit_event("1"), _audit_event("1"), after="next"),
        _audit_page(_audit_event("1"), _audit_event("2")),
    ]

    teams = await _collect_changed(TeamExporter(mock_datadog_client))

    assert teams == [_team("1"), _team("2")]
    assert mock_get_resource.await_count == 2
    second_body = mock_request.call_args_list[1].kwargs["json_data"]
    assert second_body["page"] == {"limit": MAX_PAGE_SIZE, "cursor": "next"}


@pytest.mark.asyncio
async def test_get_changed_teams_yields_one_batch_per_concurrent_fetch(
    mock_datadog_client: DatadogClient,
    team_audit_mocks: tuple[AsyncMock, AsyncMock],
) -> None:
    mock_request, _ = team_audit_mocks
    team_ids = [str(i) for i in range(CHANGED_RESOURCES_FETCH_BATCH_SIZE + 1)]
    mock_request.return_value = _audit_page(*(_audit_event(i) for i in team_ids))

    batches = [
        batch
        async for batch in TeamExporter(mock_datadog_client).get_changed_teams(
            ListTeamOptions(), incremental_cursor=SINCE
        )
    ]

    assert [len(batch) for batch in batches] == [CHANGED_RESOURCES_FETCH_BATCH_SIZE, 1]
    assert [team for batch in batches for team in batch] == [_team(i) for i in team_ids]


@pytest.mark.asyncio
@pytest.mark.parametrize("include_members", [True, False])
async def test_get_changed_teams_passes_include_members(
    mock_datadog_client: DatadogClient,
    team_audit_mocks: tuple[AsyncMock, AsyncMock],
    include_members: bool,
) -> None:
    mock_request, mock_get_resource = team_audit_mocks
    mock_request.return_value = _audit_page(_audit_event("1"))

    await _collect_changed(
        TeamExporter(mock_datadog_client),
        ListTeamOptions(include_members=include_members),
    )

    mock_get_resource.assert_awaited_once_with(
        GetTeamOptions(resource_id="1", include_members=include_members)
    )


@pytest.mark.asyncio
async def test_get_changed_teams_skips_teams_that_no_longer_exist(
    mock_datadog_client: DatadogClient,
    team_audit_mocks: tuple[AsyncMock, AsyncMock],
) -> None:
    mock_request, mock_get_resource = team_audit_mocks
    mock_request.return_value = _audit_page(_audit_event("1"), _audit_event("2"))
    mock_get_resource.side_effect = [_http_error(404), _team("2")]

    teams = await _collect_changed(TeamExporter(mock_datadog_client))

    assert teams == [_team("2")]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 500])
async def test_get_changed_teams_raises_other_fetch_errors(
    mock_datadog_client: DatadogClient,
    team_audit_mocks: tuple[AsyncMock, AsyncMock],
    status: int,
) -> None:
    mock_request, mock_get_resource = team_audit_mocks
    mock_request.return_value = _audit_page(_audit_event("1"), _audit_event("2"))
    mock_get_resource.side_effect = [_http_error(status), _team("2")]

    with pytest.raises(httpx.HTTPStatusError):
        await _collect_changed(TeamExporter(mock_datadog_client))
