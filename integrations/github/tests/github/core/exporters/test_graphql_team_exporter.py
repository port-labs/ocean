from typing import Any, AsyncGenerator
import httpx
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
import pytest
from unittest.mock import patch, MagicMock
from github.clients.http.graphql_client import GithubGraphQLClient
from github.core.exporters.graphql_team_exporter import GraphQLTeamExporter
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context
from github.core.options import SingleTeamOptions
from github.helpers.gql_queries import (
    LIST_TEAM_MEMBERS_GQL,
    FETCH_TEAM_WITH_MEMBERS_GQL,
)


TEST_TEAMS = [
    {
        "id": 1,
        "slug": "team-alpha",
        "name": "Team Alpha",
        "description": "Alpha team",
        "members": {"nodes": []},
    },
    {
        "id": 2,
        "slug": "team-beta",
        "name": "Team Beta",
        "description": "Beta team",
        "members": {"nodes": []},
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
class TestGraphQLTeamExporter:
    async def test_get_resource(self, graphql_client: GithubGraphQLClient) -> None:
        # Create a mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"organization": {"team": TEST_TEAMS[0]}}
        }

        exporter = GraphQLTeamExporter(graphql_client)

        with patch.object(
            graphql_client, "send_api_request", return_value=mock_response
        ) as mock_request:
            team = await exporter.get_resource(SingleTeamOptions(slug="team-alpha"))

            assert team == TEST_TEAMS[0]

            expected_variables = {
                "slug": "team-alpha",
                "organization": graphql_client.organization,
            }
            expected_payload = graphql_client.build_graphql_payload(
                query=FETCH_TEAM_WITH_MEMBERS_GQL, variables=expected_variables
            )
            mock_request.assert_called_once_with(
                graphql_client.base_url, method="POST", json_data=expected_payload
            )

    async def test_get_paginated_resources(
        self,
        graphql_client: GithubGraphQLClient,
    ) -> None:
        # Create an async mock to return the test teams
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_TEAMS

        with patch.object(
            graphql_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                exporter = GraphQLTeamExporter(graphql_client)

                teams: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources()
                ]

                assert len(teams) == 1
                assert len(teams[0]) == 2
                assert teams[0] == TEST_TEAMS

                expected_variables = {
                    "organization": graphql_client.organization,
                    "__path": "organization.teams",
                }
                mock_request.assert_called_once_with(
                    LIST_TEAM_MEMBERS_GQL, expected_variables
                )
