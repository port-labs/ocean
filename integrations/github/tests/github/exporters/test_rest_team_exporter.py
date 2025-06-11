from typing import Any, AsyncGenerator
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
import pytest
from unittest.mock import patch
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.rest_team_exporter import (
    RestTeamExporter,
)
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context
from github.core.options import SingleTeamOptions


TEST_TEAMS = [
    {
        "id": 1,
        "slug": "team-alpha",
        "name": "Team Alpha",
        "description": "Alpha team",
    },
    {
        "id": 2,
        "slug": "team-beta",
        "name": "Team Beta",
        "description": "Beta team",
    },
]


@pytest.fixture
def mock_port_app_config() -> GithubPortAppConfig:
    return GithubPortAppConfig(
        delete_dependent_entities=True,
        create_missing_related_entities=False,
        resources=[
            ResourceConfig(
                kind="team",
                selector=Selector(query="true"),
                port=PortResourceConfig(
                    entity=MappingsConfig(
                        mappings=EntityMapping(
                            identifier=".slug",
                            title=".name",
                            blueprint='"githubTeam"',
                            properties={},
                        )
                    )
                ),
            )
        ],
    )


@pytest.mark.asyncio
class TestRestTeamExporter:
    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        exporter = RestTeamExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", return_value=TEST_TEAMS[0]
        ) as mock_request:
            team = await exporter.get_resource(SingleTeamOptions(slug="team-alpha"))

            assert team == TEST_TEAMS[0]

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/orgs/{rest_client.organization}/teams/team-alpha"
            )

    async def test_get_paginated_resources(self, rest_client: GithubRestClient) -> None:
        # Create an async mock to return the test teams
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_TEAMS

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                exporter = RestTeamExporter(rest_client)

                teams: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources()
                ]

                assert len(teams) == 1
                assert len(teams[0]) == 2
                assert teams[0] == TEST_TEAMS

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/orgs/{rest_client.organization}/teams"
                )
