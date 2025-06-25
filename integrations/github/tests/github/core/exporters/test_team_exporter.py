import copy
from typing import Any, AsyncGenerator, Iterator
import httpx
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from github.clients.http.graphql_client import GithubGraphQLClient
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.team_exporter import (
    RestTeamExporter,
    GraphQLTeamWithMembersExporter,
)
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


MEMBER_PAGE_SIZE_IN_EXPORTER = 10

TEAM_ALPHA_MEMBERS_PAGE1_NODES = [
    {
        "login": f"member_alpha_{i + 1}",
        "email": f"member_alpha_{i + 1}@example.com",
        "isSiteAdmin": False,
    }
    for i in range(MEMBER_PAGE_SIZE_IN_EXPORTER)
]
TEAM_ALPHA_MEMBERS_PAGE1_PAGEINFO = {
    "hasNextPage": True,
    "endCursor": "cursor_alpha_p1",
}

TEAM_ALPHA_MEMBERS_PAGE2_NODES = [
    {
        "login": "member_alpha_last",
        "email": "member_alpha_last@example.com",
        "isSiteAdmin": False,
    }
]
TEAM_ALPHA_MEMBERS_PAGE2_PAGEINFO = {
    "hasNextPage": False,
    "endCursor": "cursor_alpha_p2",
}

TEAM_ALPHA_ALL_MEMBERS_NODES = (
    TEAM_ALPHA_MEMBERS_PAGE1_NODES + TEAM_ALPHA_MEMBERS_PAGE2_NODES
)

TEAM_ALPHA_INITIAL = {
    "id": "T_ALPHA",
    "slug": "team-alpha",
    "name": "Team Alpha",
    "description": "Alpha team with paginated members",
    "privacy": "VISIBLE",
    "notificationSetting": "NOTIFICATIONS_ENABLED",
    "url": "https://github.com/org/test-org/teams/team-alpha",
    "members": {
        "nodes": TEAM_ALPHA_MEMBERS_PAGE1_NODES,
        "pageInfo": TEAM_ALPHA_MEMBERS_PAGE1_PAGEINFO,
    },
}

# Team Alpha - Resolved state (all members fetched)
TEAM_ALPHA_RESOLVED = {
    "id": "T_ALPHA",
    "slug": "team-alpha",
    "name": "Team Alpha",
    "description": "Alpha team with paginated members",
    "privacy": "VISIBLE",
    "notificationSetting": "NOTIFICATIONS_ENABLED",
    "url": "https://github.com/org/test-org/teams/team-alpha",
    "members": {"nodes": TEAM_ALPHA_ALL_MEMBERS_NODES},  # pageInfo is removed
}

# Team Beta - No member pagination needed for this example
TEAM_BETA_MEMBER_NODES = [
    {
        "login": "member_beta_1",
        "email": "member_beta_1@example.com",
        "isSiteAdmin": True,
    }
]
TEAM_BETA_INITIAL = {
    "id": "T_BETA",
    "slug": "team-beta",
    "name": "Team Beta",
    "description": "Beta team, no member pagination",
    "privacy": "SECRET",
    "notificationSetting": "NOTIFICATIONS_DISABLED",
    "url": "https://github.com/org/test-org/teams/team-beta",
    "members": {
        "nodes": TEAM_BETA_MEMBER_NODES,
        "pageInfo": {"hasNextPage": False, "endCursor": None},
    },
}

TEAM_BETA_RESOLVED = {
    "id": "T_BETA",
    "slug": "team-beta",
    "name": "Team Beta",
    "description": "Beta team, no member pagination",
    "privacy": "SECRET",
    "notificationSetting": "NOTIFICATIONS_DISABLED",
    "url": "https://github.com/org/test-org/teams/team-beta",
    "members": {"nodes": TEAM_BETA_MEMBER_NODES},  # pageInfo is removed
}


GET_RESOURCE_TEAM_ALPHA_PAGE1_RESPONSE = {
    "data": {"organization": {"team": TEAM_ALPHA_INITIAL}}
}
GET_RESOURCE_TEAM_ALPHA_PAGE2_RESPONSE = {
    "data": {
        "organization": {
            "team": {
                # Only members part is crucial for the second fetch
                "slug": "team-alpha",
                "id": "T_ALPHA",
                "name": "Team Alpha",
                "description": "Alpha team with paginated members",
                "privacy": "VISIBLE",
                "notificationSetting": "NOTIFICATIONS_ENABLED",
                "url": "https://github.com/org/test-org/teams/team-alpha",
                "members": {
                    "nodes": TEAM_ALPHA_MEMBERS_PAGE2_NODES,
                    "pageInfo": TEAM_ALPHA_MEMBERS_PAGE2_PAGEINFO,
                },
            }
        }
    }
}


@pytest.mark.asyncio
class TestGraphQLTeamExporter:
    @pytest.fixture(autouse=True)
    def patch_page_size(self) -> Iterator[None]:
        with patch.object(
            GraphQLTeamWithMembersExporter,
            "MEMBER_PAGE_SIZE",
            MEMBER_PAGE_SIZE_IN_EXPORTER,
        ):
            yield

    async def test_get_resource_with_member_pagination(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        mock_send_api_request = AsyncMock(
            side_effect=[
                MagicMock(
                    spec=httpx.Response,
                    status_code=200,
                    json=lambda: copy.deepcopy(GET_RESOURCE_TEAM_ALPHA_PAGE1_RESPONSE),
                ),
                MagicMock(
                    spec=httpx.Response,
                    status_code=200,
                    json=lambda: copy.deepcopy(GET_RESOURCE_TEAM_ALPHA_PAGE2_RESPONSE),
                ),
            ]
        )

        exporter = GraphQLTeamWithMembersExporter(graphql_client)

        with patch.object(
            graphql_client, "send_api_request", new=mock_send_api_request
        ):
            team = await exporter.get_resource(SingleTeamOptions(slug="team-alpha"))

            assert team == TEAM_ALPHA_RESOLVED
            assert mock_send_api_request.call_count == 2

            call_args_initial = mock_send_api_request.call_args_list[0]
            expected_variables_initial = {
                "slug": "team-alpha",
                "organization": graphql_client.organization,
                "memberFirst": MEMBER_PAGE_SIZE_IN_EXPORTER,
            }
            expected_payload_initial = graphql_client.build_graphql_payload(
                query=FETCH_TEAM_WITH_MEMBERS_GQL, variables=expected_variables_initial
            )
            assert call_args_initial[0][0] == graphql_client.base_url
            assert call_args_initial[1]["method"] == "POST"
            assert call_args_initial[1]["json_data"] == expected_payload_initial

            # Assertions for the second call (triggered by fetch_other_members)
            call_args_page2 = mock_send_api_request.call_args_list[1]
            expected_variables_page2 = {
                "slug": "team-alpha",
                "organization": graphql_client.organization,
                "memberFirst": MEMBER_PAGE_SIZE_IN_EXPORTER,
                "memberAfter": TEAM_ALPHA_MEMBERS_PAGE1_PAGEINFO["endCursor"],
            }
            expected_payload_page2 = graphql_client.build_graphql_payload(
                query=FETCH_TEAM_WITH_MEMBERS_GQL, variables=expected_variables_page2
            )
            assert call_args_page2[0][0] == graphql_client.base_url
            assert call_args_page2[1]["method"] == "POST"
            assert call_args_page2[1]["json_data"] == expected_payload_page2

    async def test_get_resource_no_member_pagination(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        mock_response_beta = MagicMock(spec=httpx.Response)
        mock_response_beta.status_code = 200
        mock_response_beta.json.return_value = copy.deepcopy(
            {"data": {"organization": {"team": TEAM_BETA_INITIAL}}}
        )

        exporter = GraphQLTeamWithMembersExporter(graphql_client)
        with patch.object(
            graphql_client,
            "send_api_request",
            new=AsyncMock(return_value=mock_response_beta),
        ) as mock_request:
            team = await exporter.get_resource(SingleTeamOptions(slug="team-beta"))

            assert team == TEAM_BETA_RESOLVED
            mock_request.assert_called_once()

    async def test_get_paginated_resources_with_member_pagination(
        self,
        graphql_client: GithubGraphQLClient,
    ) -> None:
        teams_to_yield_original = [TEAM_ALPHA_INITIAL, TEAM_BETA_INITIAL]

        async def mock_send_paginated_request_teams(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield copy.deepcopy(teams_to_yield_original)

        exporter = GraphQLTeamWithMembersExporter(graphql_client)

        # Mock fetch_other_members for team-alpha
        mock_fetch_other_members = AsyncMock(
            return_value=TEAM_ALPHA_ALL_MEMBERS_NODES  # fetch_other_members returns only nodes
        )

        with (
            patch.object(
                graphql_client,
                "send_paginated_request",
                side_effect=mock_send_paginated_request_teams,
            ) as mock_gql_paginated_req,
            patch.object(
                exporter, "get_paginated_members", new=mock_fetch_other_members
            ) as mock_exporter_fetch_members,
        ):
            result_batches: list[list[dict[str, Any]]] = [
                batch async for batch in exporter.get_paginated_resources()
            ]

            assert len(result_batches) == 1
            assert len(result_batches[0]) == 2

            assert result_batches[0][0] == TEAM_ALPHA_RESOLVED
            assert result_batches[0][1] == TEAM_BETA_RESOLVED

            # Assert send_paginated_request (for teams) was called correctly
            expected_variables_for_teams_fetch = {
                "organization": graphql_client.organization,
                "__path": "organization.teams",
                "memberFirst": MEMBER_PAGE_SIZE_IN_EXPORTER,
            }
            mock_gql_paginated_req.assert_called_once_with(
                LIST_TEAM_MEMBERS_GQL, params=expected_variables_for_teams_fetch
            )

            # Assert fetch_other_members was called for Team Alpha
            mock_exporter_fetch_members.assert_called_once_with(
                team_slug="team-alpha",
                initial_members_page_info=TEAM_ALPHA_MEMBERS_PAGE1_PAGEINFO,
                initial_member_nodes=TEAM_ALPHA_MEMBERS_PAGE1_NODES,
                member_page_size=MEMBER_PAGE_SIZE_IN_EXPORTER,
            )
