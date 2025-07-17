import copy
from typing import Any, AsyncGenerator, Dict, Iterator
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
import pytest
from unittest.mock import AsyncMock, patch
from github.clients.http.graphql_client import GithubGraphQLClient
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.team_exporter import (
    RestTeamExporter,
    GraphQLTeamWithMembersExporter,
    GraphQLTeamMembersAndReposExporter,
)
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context
from github.core.options import SingleTeamOptions

from github.helpers.gql_queries import (
    LIST_TEAM_MEMBERS_GQL,
    FETCH_TEAM_WITH_MEMBERS_GQL,
    SINGLE_TEAM_WITH_MEMBERS_AND_REPOS_GQL,
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
        "id": f"MEMBER_ALPHA_{i + 1}",
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
        "id": "MEMBER_ALPHA_LAST",
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
        "id": "MEMBER_BETA_1",
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
                copy.deepcopy(GET_RESOURCE_TEAM_ALPHA_PAGE1_RESPONSE),
                copy.deepcopy(GET_RESOURCE_TEAM_ALPHA_PAGE2_RESPONSE),
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

        mock_response_data = copy.deepcopy(
            {"data": {"organization": {"team": TEAM_BETA_INITIAL}}}
        )

        exporter = GraphQLTeamWithMembersExporter(graphql_client)
        with patch.object(
            graphql_client,
            "send_api_request",
            new=AsyncMock(return_value=mock_response_data),
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


class TestGraphQLTeamMembersAndReposExporter:

    @pytest.fixture(autouse=True)
    def patch_page_size(self) -> Iterator[None]:
        with patch.object(
            GraphQLTeamMembersAndReposExporter,
            "PAGE_SIZE",
            MEMBER_PAGE_SIZE_IN_EXPORTER,
        ):
            yield

    async def test_get_team_member_repositories_no_pagination(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test get_team_member_repositories when no pagination is needed."""
        team_with_members_and_repos: Dict[str, Any] = {
            "id": "T_GAMMA",
            "slug": "team-gamma",
            "name": "Team Gamma",
            "description": "Gamma team with members and repos",
            "privacy": "VISIBLE",
            "notificationSetting": "NOTIFICATIONS_ENABLED",
            "url": "https://github.com/org/test-org/teams/team-gamma",
            "members": {
                "nodes": [
                    {
                        "id": "MEMBER_GAMMA_1",
                        "login": "member_gamma_1",
                        "email": "member_gamma_1@example.com",
                        "isSiteAdmin": False,
                    }
                ],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            },
            "repositories": {
                "nodes": [
                    {
                        "id": "R_GAMMA_1",
                        "name": "repo-gamma-1",
                        "nameWithOwner": "test-org/repo-gamma-1",
                        "description": "First gamma repository",
                        "url": "https://github.com/test-org/repo-gamma-1",
                        "homepageUrl": None,
                        "isPrivate": False,
                        "createdAt": "2023-01-01T00:00:00Z",
                        "updatedAt": "2023-01-02T00:00:00Z",
                        "pushedAt": "2023-01-03T00:00:00Z",
                        "defaultBranchRef": {"name": "main"},
                        "primaryLanguage": {"name": "Python"},
                        "visibility": "PUBLIC",
                    }
                ],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            },
        }

        expected_result = {
            "id": "T_GAMMA",
            "slug": "team-gamma",
            "name": "Team Gamma",
            "description": "Gamma team with members and repos",
            "privacy": "VISIBLE",
            "notificationSetting": "NOTIFICATIONS_ENABLED",
            "url": "https://github.com/org/test-org/teams/team-gamma",
            "members": {"nodes": team_with_members_and_repos["members"]["nodes"]},
            "repositories": {
                "nodes": team_with_members_and_repos["repositories"]["nodes"]
            },
        }

        mock_response_data = copy.deepcopy(
            {"data": {"organization": {"team": team_with_members_and_repos}}}
        )

        exporter = GraphQLTeamMembersAndReposExporter(graphql_client)
        with patch.object(
            graphql_client,
            "send_api_request",
            new=AsyncMock(return_value=mock_response_data),
        ) as mock_request:
            result = await exporter.get_resource(SingleTeamOptions(slug="team-gamma"))

            assert result == expected_result
            mock_request.assert_called_once()

            # Verify the GraphQL payload
            call_args = mock_request.call_args
            expected_variables = {
                "slug": "team-gamma",
                "organization": graphql_client.organization,
                "memberFirst": MEMBER_PAGE_SIZE_IN_EXPORTER,
                "memberAfter": None,
                "repoFirst": MEMBER_PAGE_SIZE_IN_EXPORTER,
                "repoAfter": None,
            }
            expected_payload = graphql_client.build_graphql_payload(
                query=SINGLE_TEAM_WITH_MEMBERS_AND_REPOS_GQL,
                variables=expected_variables,
            )
            assert call_args[0][0] == graphql_client.base_url
            assert call_args[1]["method"] == "POST"
            assert call_args[1]["json_data"] == expected_payload

    async def test_get_team_member_repositories_with_member_pagination(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test get_team_member_repositories when member pagination is needed."""
        # First page response
        team_page1: Dict[str, Any] = {
            "id": "T_DELTA",
            "slug": "team-delta",
            "name": "Team Delta",
            "description": "Delta team with paginated members",
            "privacy": "SECRET",
            "notificationSetting": "NOTIFICATIONS_DISABLED",
            "url": "https://github.com/org/test-org/teams/team-delta",
            "members": {
                "nodes": [
                    {
                        "id": f"MEMBER_DELTA_{i + 1}",
                        "login": f"member_delta_{i + 1}",
                        "email": f"member_delta_{i + 1}@example.com",
                        "isSiteAdmin": False,
                    }
                    for i in range(MEMBER_PAGE_SIZE_IN_EXPORTER)
                ],
                "pageInfo": {
                    "hasNextPage": True,
                    "endCursor": "cursor_delta_members_p1",
                },
            },
            "repositories": {
                "nodes": [
                    {
                        "id": "R_DELTA_1",
                        "name": "repo-delta-1",
                        "nameWithOwner": "test-org/repo-delta-1",
                        "description": "First delta repository",
                        "url": "https://github.com/test-org/repo-delta-1",
                        "homepageUrl": None,
                        "isPrivate": True,
                        "createdAt": "2023-01-01T00:00:00Z",
                        "updatedAt": "2023-01-02T00:00:00Z",
                        "pushedAt": "2023-01-03T00:00:00Z",
                        "defaultBranchRef": {"name": "main"},
                        "primaryLanguage": {"name": "JavaScript"},
                        "visibility": "PRIVATE",
                    }
                ],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            },
        }

        # Second page response (only members part is crucial)
        team_page2: Dict[str, Any] = {
            "id": "T_DELTA",
            "slug": "team-delta",
            "name": "Team Delta",
            "description": "Delta team with paginated members",
            "privacy": "SECRET",
            "notificationSetting": "NOTIFICATIONS_DISABLED",
            "url": "https://github.com/org/test-org/teams/team-delta",
            "members": {
                "nodes": [
                    {
                        "id": "MEMBER_DELTA_LAST",
                        "login": "member_delta_last",
                        "email": "member_delta_last@example.com",
                        "isSiteAdmin": True,
                    }
                ],
                "pageInfo": {
                    "hasNextPage": False,
                    "endCursor": "cursor_delta_members_p2",
                },
            },
            "repositories": {
                "nodes": [],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            },
        }

        all_members = list(team_page1["members"]["nodes"]) + list(
            team_page2["members"]["nodes"]
        )
        all_repos = list(team_page1["repositories"]["nodes"])

        expected_result = {
            "id": "T_DELTA",
            "slug": "team-delta",
            "name": "Team Delta",
            "description": "Delta team with paginated members",
            "privacy": "SECRET",
            "notificationSetting": "NOTIFICATIONS_DISABLED",
            "url": "https://github.com/org/test-org/teams/team-delta",
            "members": {"nodes": all_members},
            "repositories": {"nodes": all_repos},
        }

        mock_send_api_request = AsyncMock(
            side_effect=[
                copy.deepcopy({"data": {"organization": {"team": team_page1}}}),
                copy.deepcopy({"data": {"organization": {"team": team_page2}}}),
            ]
        )

        exporter = GraphQLTeamMembersAndReposExporter(graphql_client)
        with patch.object(
            graphql_client, "send_api_request", new=mock_send_api_request
        ):
            result = await exporter.get_resource(SingleTeamOptions(slug="team-delta"))

            assert result == expected_result
            assert mock_send_api_request.call_count == 2

            # Verify first call
            call_args_1 = mock_send_api_request.call_args_list[0]
            expected_variables_1 = {
                "slug": "team-delta",
                "organization": graphql_client.organization,
                "memberFirst": MEMBER_PAGE_SIZE_IN_EXPORTER,
                "memberAfter": None,
                "repoFirst": MEMBER_PAGE_SIZE_IN_EXPORTER,
                "repoAfter": None,
            }
            expected_payload_1 = graphql_client.build_graphql_payload(
                query=SINGLE_TEAM_WITH_MEMBERS_AND_REPOS_GQL,
                variables=expected_variables_1,
            )
            assert call_args_1[0][0] == graphql_client.base_url
            assert call_args_1[1]["method"] == "POST"
            assert call_args_1[1]["json_data"] == expected_payload_1

            # Verify second call
            call_args_2 = mock_send_api_request.call_args_list[1]
            expected_variables_2 = {
                "slug": "team-delta",
                "organization": graphql_client.organization,
                "memberFirst": MEMBER_PAGE_SIZE_IN_EXPORTER,
                "memberAfter": "cursor_delta_members_p1",
                "repoFirst": MEMBER_PAGE_SIZE_IN_EXPORTER,
                "repoAfter": None,
            }
            expected_payload_2 = graphql_client.build_graphql_payload(
                query=SINGLE_TEAM_WITH_MEMBERS_AND_REPOS_GQL,
                variables=expected_variables_2,
            )
            assert call_args_2[0][0] == graphql_client.base_url
            assert call_args_2[1]["method"] == "POST"
            assert call_args_2[1]["json_data"] == expected_payload_2

    async def test_get_team_member_repositories_with_repo_pagination(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test get_team_member_repositories when repository pagination is needed."""
        # First page response
        team_page1: Dict[str, Any] = {
            "id": "T_EPSILON",
            "slug": "team-epsilon",
            "name": "Team Epsilon",
            "description": "Epsilon team with paginated repos",
            "privacy": "VISIBLE",
            "notificationSetting": "NOTIFICATIONS_ENABLED",
            "url": "https://github.com/org/test-org/teams/team-epsilon",
            "members": {
                "nodes": [
                    {
                        "id": "MEMBER_EPSILON_1",
                        "login": "member_epsilon_1",
                        "email": "member_epsilon_1@example.com",
                        "isSiteAdmin": False,
                    }
                ],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            },
            "repositories": {
                "nodes": [
                    {
                        "id": "R_EPSILON_1",
                        "name": "repo-epsilon-1",
                        "nameWithOwner": "test-org/repo-epsilon-1",
                        "description": "First epsilon repository",
                        "url": "https://github.com/test-org/repo-epsilon-1",
                        "homepageUrl": None,
                        "isPrivate": False,
                        "createdAt": "2023-01-01T00:00:00Z",
                        "updatedAt": "2023-01-02T00:00:00Z",
                        "pushedAt": "2023-01-03T00:00:00Z",
                        "defaultBranchRef": {"name": "main"},
                        "primaryLanguage": {"name": "Python"},
                        "visibility": "PUBLIC",
                    },
                    {
                        "id": "R_EPSILON_2",
                        "name": "repo-epsilon-2",
                        "nameWithOwner": "test-org/repo-epsilon-2",
                        "description": "Second epsilon repository",
                        "url": "https://github.com/test-org/repo-epsilon-2",
                        "homepageUrl": None,
                        "isPrivate": True,
                        "createdAt": "2023-01-04T00:00:00Z",
                        "updatedAt": "2023-01-05T00:00:00Z",
                        "pushedAt": "2023-01-06T00:00:00Z",
                        "defaultBranchRef": {"name": "develop"},
                        "primaryLanguage": {"name": "TypeScript"},
                        "visibility": "PRIVATE",
                    },
                ],
                "pageInfo": {
                    "hasNextPage": True,
                    "endCursor": "cursor_epsilon_repos_p1",
                },
            },
        }

        # Second page response (only repos part is crucial)
        team_page2: Dict[str, Any] = {
            "id": "T_EPSILON",
            "slug": "team-epsilon",
            "name": "Team Epsilon",
            "description": "Epsilon team with paginated repos",
            "privacy": "VISIBLE",
            "notificationSetting": "NOTIFICATIONS_ENABLED",
            "url": "https://github.com/org/test-org/teams/team-epsilon",
            "members": {
                "nodes": [
                    {
                        "id": "MEMBER_EPSILON_1",
                        "login": "member_epsilon_1",
                        "email": "member_epsilon_1@example.com",
                        "isSiteAdmin": False,
                    }
                ],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            },
            "repositories": {
                "nodes": [
                    {
                        "id": "R_EPSILON_3",
                        "name": "repo-epsilon-3",
                        "nameWithOwner": "test-org/repo-epsilon-3",
                        "description": "Third epsilon repository",
                        "url": "https://github.com/test-org/repo-epsilon-3",
                        "homepageUrl": None,
                        "isPrivate": False,
                        "createdAt": "2023-01-07T00:00:00Z",
                        "updatedAt": "2023-01-08T00:00:00Z",
                        "pushedAt": "2023-01-09T00:00:00Z",
                        "defaultBranchRef": {"name": "main"},
                        "primaryLanguage": {"name": "Go"},
                        "visibility": "PUBLIC",
                    }
                ],
                "pageInfo": {
                    "hasNextPage": False,
                    "endCursor": "cursor_epsilon_repos_p2",
                },
            },
        }

        all_members = list(team_page1["members"]["nodes"])
        all_repos = list(team_page1["repositories"]["nodes"]) + list(
            team_page2["repositories"]["nodes"]
        )

        expected_result = {
            "id": "T_EPSILON",
            "slug": "team-epsilon",
            "name": "Team Epsilon",
            "description": "Epsilon team with paginated repos",
            "privacy": "VISIBLE",
            "notificationSetting": "NOTIFICATIONS_ENABLED",
            "url": "https://github.com/org/test-org/teams/team-epsilon",
            "members": {"nodes": all_members},
            "repositories": {"nodes": all_repos},
        }

        mock_send_api_request = AsyncMock(
            side_effect=[
                copy.deepcopy({"data": {"organization": {"team": team_page1}}}),
                copy.deepcopy({"data": {"organization": {"team": team_page2}}}),
            ]
        )

        exporter = GraphQLTeamMembersAndReposExporter(graphql_client)
        with patch.object(
            graphql_client, "send_api_request", new=mock_send_api_request
        ):
            result = await exporter.get_resource(SingleTeamOptions(slug="team-epsilon"))

            assert result == expected_result
            assert mock_send_api_request.call_count == 2

            # Verify first call
            call_args_1 = mock_send_api_request.call_args_list[0]
            expected_variables_1 = {
                "slug": "team-epsilon",
                "organization": graphql_client.organization,
                "memberFirst": MEMBER_PAGE_SIZE_IN_EXPORTER,
                "memberAfter": None,
                "repoFirst": MEMBER_PAGE_SIZE_IN_EXPORTER,
                "repoAfter": None,
            }
            expected_payload_1 = graphql_client.build_graphql_payload(
                query=SINGLE_TEAM_WITH_MEMBERS_AND_REPOS_GQL,
                variables=expected_variables_1,
            )
            assert call_args_1[0][0] == graphql_client.base_url
            assert call_args_1[1]["method"] == "POST"
            assert call_args_1[1]["json_data"] == expected_payload_1

            # Verify second call
            call_args_2 = mock_send_api_request.call_args_list[1]
            expected_variables_2 = {
                "slug": "team-epsilon",
                "organization": graphql_client.organization,
                "memberFirst": MEMBER_PAGE_SIZE_IN_EXPORTER,
                "memberAfter": None,
                "repoFirst": MEMBER_PAGE_SIZE_IN_EXPORTER,
                "repoAfter": "cursor_epsilon_repos_p1",
            }
            expected_payload_2 = graphql_client.build_graphql_payload(
                query=SINGLE_TEAM_WITH_MEMBERS_AND_REPOS_GQL,
                variables=expected_variables_2,
            )
            assert call_args_2[0][0] == graphql_client.base_url
            assert call_args_2[1]["method"] == "POST"
            assert call_args_2[1]["json_data"] == expected_payload_2

    async def test_get_team_member_repositories_with_both_paginations(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test get_team_member_repositories when both member and repo pagination are needed."""
        # First page response
        team_page1: Dict[str, Any] = {
            "id": "T_ZETA",
            "slug": "team-zeta",
            "name": "Team Zeta",
            "description": "Zeta team with both paginations",
            "privacy": "SECRET",
            "notificationSetting": "NOTIFICATIONS_DISABLED",
            "url": "https://github.com/org/test-org/teams/team-zeta",
            "members": {
                "nodes": [
                    {
                        "id": f"MEMBER_ZETA_{i + 1}",
                        "login": f"member_zeta_{i + 1}",
                        "email": f"member_zeta_{i + 1}@example.com",
                        "isSiteAdmin": False,
                    }
                    for i in range(MEMBER_PAGE_SIZE_IN_EXPORTER)
                ],
                "pageInfo": {
                    "hasNextPage": True,
                    "endCursor": "cursor_zeta_members_p1",
                },
            },
            "repositories": {
                "nodes": [
                    {
                        "id": "R_ZETA_1",
                        "name": "repo-zeta-1",
                        "nameWithOwner": "test-org/repo-zeta-1",
                        "description": "First zeta repository",
                        "url": "https://github.com/test-org/repo-zeta-1",
                        "homepageUrl": None,
                        "isPrivate": False,
                        "createdAt": "2023-01-01T00:00:00Z",
                        "updatedAt": "2023-01-02T00:00:00Z",
                        "pushedAt": "2023-01-03T00:00:00Z",
                        "defaultBranchRef": {"name": "main"},
                        "primaryLanguage": {"name": "Python"},
                        "visibility": "PUBLIC",
                    },
                    {
                        "id": "R_ZETA_2",
                        "name": "repo-zeta-2",
                        "nameWithOwner": "test-org/repo-zeta-2",
                        "description": "Second zeta repository",
                        "url": "https://github.com/test-org/repo-zeta-2",
                        "homepageUrl": None,
                        "isPrivate": True,
                        "createdAt": "2023-01-04T00:00:00Z",
                        "updatedAt": "2023-01-05T00:00:00Z",
                        "pushedAt": "2023-01-06T00:00:00Z",
                        "defaultBranchRef": {"name": "develop"},
                        "primaryLanguage": {"name": "TypeScript"},
                        "visibility": "PRIVATE",
                    },
                ],
                "pageInfo": {"hasNextPage": True, "endCursor": "cursor_zeta_repos_p1"},
            },
        }

        # Second page response (continue with member pagination)
        team_page2: Dict[str, Any] = {
            "id": "T_ZETA",
            "slug": "team-zeta",
            "name": "Team Zeta",
            "description": "Zeta team with both paginations",
            "privacy": "SECRET",
            "notificationSetting": "NOTIFICATIONS_DISABLED",
            "url": "https://github.com/org/test-org/teams/team-zeta",
            "members": {
                "nodes": [
                    {
                        "id": "MEMBER_ZETA_LAST",
                        "login": "member_zeta_last",
                        "email": "member_zeta_last@example.com",
                        "isSiteAdmin": True,
                    }
                ],
                "pageInfo": {
                    "hasNextPage": False,
                    "endCursor": "cursor_zeta_members_p2",
                },
            },
            "repositories": {
                "nodes": [],
                "pageInfo": {"hasNextPage": True, "endCursor": "cursor_zeta_repos_p1"},
            },
        }

        # Third page response (continue with repo pagination)
        team_page3: Dict[str, Any] = {
            "id": "T_ZETA",
            "slug": "team-zeta",
            "name": "Team Zeta",
            "description": "Zeta team with both paginations",
            "privacy": "SECRET",
            "notificationSetting": "NOTIFICATIONS_DISABLED",
            "url": "https://github.com/org/test-org/teams/team-zeta",
            "members": {
                "nodes": [
                    {
                        "id": "MEMBER_ZETA_LAST",
                        "login": "member_zeta_last",
                        "email": "member_zeta_last@example.com",
                        "isSiteAdmin": True,
                    }
                ],
                "pageInfo": {
                    "hasNextPage": False,
                    "endCursor": "cursor_zeta_members_p2",
                },
            },
            "repositories": {
                "nodes": [
                    {
                        "id": "R_ZETA_3",
                        "name": "repo-zeta-3",
                        "nameWithOwner": "test-org/repo-zeta-3",
                        "description": "Third zeta repository",
                        "url": "https://github.com/test-org/repo-zeta-3",
                        "homepageUrl": None,
                        "isPrivate": False,
                        "createdAt": "2023-01-07T00:00:00Z",
                        "updatedAt": "2023-01-08T00:00:00Z",
                        "pushedAt": "2023-01-09T00:00:00Z",
                        "defaultBranchRef": {"name": "main"},
                        "primaryLanguage": {"name": "Go"},
                        "visibility": "PUBLIC",
                    }
                ],
                "pageInfo": {"hasNextPage": False, "endCursor": "cursor_zeta_repos_p2"},
            },
        }

        all_members = list(team_page1["members"]["nodes"]) + list(
            team_page2["members"]["nodes"]
        )
        all_repos = list(team_page1["repositories"]["nodes"]) + list(
            team_page3["repositories"]["nodes"]
        )

        expected_result = {
            "id": "T_ZETA",
            "slug": "team-zeta",
            "name": "Team Zeta",
            "description": "Zeta team with both paginations",
            "privacy": "SECRET",
            "notificationSetting": "NOTIFICATIONS_DISABLED",
            "url": "https://github.com/org/test-org/teams/team-zeta",
            "members": {"nodes": all_members},
            "repositories": {"nodes": all_repos},
        }

        mock_send_api_request = AsyncMock(
            side_effect=[
                copy.deepcopy({"data": {"organization": {"team": team_page1}}}),
                copy.deepcopy({"data": {"organization": {"team": team_page2}}}),
                copy.deepcopy({"data": {"organization": {"team": team_page3}}}),
            ]
        )

        exporter = GraphQLTeamMembersAndReposExporter(graphql_client)
        with patch.object(
            graphql_client, "send_api_request", new=mock_send_api_request
        ):
            result = await exporter.get_resource(SingleTeamOptions(slug="team-zeta"))

            assert result == expected_result
            assert mock_send_api_request.call_count == 3

            # Verify first call
            call_args_1 = mock_send_api_request.call_args_list[0]
            expected_variables_1 = {
                "slug": "team-zeta",
                "organization": graphql_client.organization,
                "memberFirst": MEMBER_PAGE_SIZE_IN_EXPORTER,
                "memberAfter": None,
                "repoFirst": MEMBER_PAGE_SIZE_IN_EXPORTER,
                "repoAfter": None,
            }
            expected_payload_1 = graphql_client.build_graphql_payload(
                query=SINGLE_TEAM_WITH_MEMBERS_AND_REPOS_GQL,
                variables=expected_variables_1,
            )
            assert call_args_1[0][0] == graphql_client.base_url
            assert call_args_1[1]["method"] == "POST"
            assert call_args_1[1]["json_data"] == expected_payload_1

            # Verify second call (member pagination)
            call_args_2 = mock_send_api_request.call_args_list[1]
            expected_variables_2 = {
                "slug": "team-zeta",
                "organization": graphql_client.organization,
                "memberFirst": MEMBER_PAGE_SIZE_IN_EXPORTER,
                "memberAfter": "cursor_zeta_members_p1",
                "repoFirst": MEMBER_PAGE_SIZE_IN_EXPORTER,
                "repoAfter": None,
            }
            expected_payload_2 = graphql_client.build_graphql_payload(
                query=SINGLE_TEAM_WITH_MEMBERS_AND_REPOS_GQL,
                variables=expected_variables_2,
            )
            assert call_args_2[0][0] == graphql_client.base_url
            assert call_args_2[1]["method"] == "POST"
            assert call_args_2[1]["json_data"] == expected_payload_2

            # Verify third call (repo pagination)
            call_args_3 = mock_send_api_request.call_args_list[2]
            expected_variables_3 = {
                "slug": "team-zeta",
                "organization": graphql_client.organization,
                "memberFirst": MEMBER_PAGE_SIZE_IN_EXPORTER,
                "memberAfter": None,
                "repoFirst": MEMBER_PAGE_SIZE_IN_EXPORTER,
                "repoAfter": "cursor_zeta_repos_p1",
            }
            expected_payload_3 = graphql_client.build_graphql_payload(
                query=SINGLE_TEAM_WITH_MEMBERS_AND_REPOS_GQL,
                variables=expected_variables_3,
            )
            assert call_args_3[0][0] == graphql_client.base_url
            assert call_args_3[1]["method"] == "POST"
            assert call_args_3[1]["json_data"] == expected_payload_3

    async def test_get_team_member_repositories_empty_response(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test get_team_member_repositories when the API returns an empty response."""
        exporter = GraphQLTeamMembersAndReposExporter(graphql_client)
        with patch.object(
            graphql_client,
            "send_api_request",
            new=AsyncMock(return_value=None),
        ) as mock_request:
            result = await exporter.get_resource(SingleTeamOptions(slug="team-empty"))

            assert result == {}
            mock_request.assert_called_once()

    async def test_get_team_member_repositories_team_not_found(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test get_team_member_repositories when the team is not found."""
        mock_response_data = {"data": {"organization": {"team": None}}}

        exporter = GraphQLTeamMembersAndReposExporter(graphql_client)
        with patch.object(
            graphql_client,
            "send_api_request",
            new=AsyncMock(return_value=mock_response_data),
        ) as mock_request:
            result = await exporter.get_resource(
                SingleTeamOptions(slug="team-not-found")
            )

            # The method should handle None team gracefully
            assert result == {}
            mock_request.assert_called_once()
