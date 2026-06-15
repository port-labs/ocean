from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from datadog.client import DatadogClient
from datadog.core.exporters.base_exporter import MAX_PAGE_SIZE
from datadog.core.exporters import TeamExporter
from datadog.core.exporters.team_exporter import ListTeamOptions


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
