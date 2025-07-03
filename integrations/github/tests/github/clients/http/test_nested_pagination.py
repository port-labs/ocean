import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import Response

from github.clients.http.graphql_client import GithubGraphQLClient
from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.helpers.exceptions import GraphQLClientError


@pytest.fixture
def graphql_client(authenticator: AbstractGitHubAuthenticator) -> GithubGraphQLClient:
    return GithubGraphQLClient(
        organization="test-org",
        github_host="https://api.github.com",
        authenticator=authenticator,
    )


@pytest.mark.asyncio
class TestNestedPagination:
    async def test_build_nested_graphql_payload(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test building GraphQL payload with nested pagination variables."""
        query = "query test($parentFirst: Int, $parentAfter: String, $childFirst: Int, $childAfter: String) { ... }"
        variables = {"organization": "test-org"}
        nested_config = {
            "parent": {"first": 25, "after": "parent_cursor"},
            "child": {"first": 50, "after": "child_cursor"},
        }

        payload = graphql_client.build_nested_graphql_payload(
            query, variables, nested_config
        )

        expected_variables = {
            "organization": "test-org",
            "parentFirst": 25,
            "parentAfter": "parent_cursor",
            "childFirst": 50,
            "childAfter": "child_cursor",
        }

        assert payload["query"] == query
        assert payload["variables"] == expected_variables

    async def test_send_nested_paginated_request_missing_config(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test that nested pagination requires proper configuration."""
        with pytest.raises(
            GraphQLClientError,
            match="Nested pagination requires both 'parent_path' and 'child_path'",
        ):
            async for _ in graphql_client.send_nested_paginated_request("query"):
                pass

    async def test_send_nested_paginated_request_single_page(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test nested pagination with single page (no additional pagination needed)."""
        # Mock response with teams that don't need member pagination
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "organization": {
                    "teams": {
                        "nodes": [
                            {
                                "slug": "team-alpha",
                                "name": "Team Alpha",
                                "members": {
                                    "nodes": [
                                        {
                                            "login": "member1",
                                            "email": "member1@example.com",
                                        }
                                    ],
                                    "pageInfo": {
                                        "hasNextPage": False,
                                        "endCursor": None,
                                    },
                                },
                            }
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }

        nested_config = {
            "parent_path": "organization.teams",
            "child_path": "members",
            "parent_page_size": 25,
            "child_page_size": 50,
        }

        with patch.object(
            graphql_client, "send_api_request", AsyncMock(return_value=mock_response)
        ):
            results = []
            async for page in graphql_client.send_nested_paginated_request(
                "query",
                params={"organization": "test-org"},
                nested_config=nested_config,
            ):
                results.append(page)

            assert len(results) == 1
            assert len(results[0]) == 1

            team = results[0][0]
            assert team["slug"] == "team-alpha"
            assert "pageInfo" not in team["members"]  # Should be cleaned up
            assert len(team["members"]["nodes"]) == 1

    async def test_send_nested_paginated_request_with_child_pagination(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test nested pagination where child data needs pagination."""
        # First response - teams with partial member data
        first_response = MagicMock(spec=Response)
        first_response.status_code = 200
        first_response.json.return_value = {
            "data": {
                "organization": {
                    "teams": {
                        "nodes": [
                            {
                                "slug": "team-alpha",
                                "name": "Team Alpha",
                                "members": {
                                    "nodes": [
                                        {
                                            "login": "member1",
                                            "email": "member1@example.com",
                                        }
                                    ],
                                    "pageInfo": {
                                        "hasNextPage": True,
                                        "endCursor": "cursor1",
                                    },
                                },
                            }
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }

        # Second response - additional members for the team
        second_response = MagicMock(spec=Response)
        second_response.status_code = 200
        second_response.json.return_value = {
            "data": {
                "organization": {
                    "team": {
                        "slug": "team-alpha",
                        "name": "Team Alpha",
                        "members": {
                            "nodes": [
                                {"login": "member2", "email": "member2@example.com"}
                            ],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        },
                    }
                }
            }
        }

        nested_config = {
            "parent_path": "organization.teams",
            "child_path": "members",
            "parent_page_size": 25,
            "child_page_size": 50,
        }

        with patch.object(
            graphql_client,
            "send_api_request",
            AsyncMock(side_effect=[first_response, second_response]),
        ):
            results = []
            async for page in graphql_client.send_nested_paginated_request(
                "query",
                params={"organization": "test-org"},
                nested_config=nested_config,
            ):
                results.append(page)

            assert len(results) == 1
            assert len(results[0]) == 1

            team = results[0][0]
            assert team["slug"] == "team-alpha"
            assert "pageInfo" not in team["members"]  # Should be cleaned up
            assert len(team["members"]["nodes"]) == 2
            assert team["members"]["nodes"][0]["login"] == "member1"
            assert team["members"]["nodes"][1]["login"] == "member2"

    async def test_send_nested_paginated_request_multiple_parent_pages(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test nested pagination with multiple parent pages."""
        # First parent page
        first_response = MagicMock(spec=Response)
        first_response.status_code = 200
        first_response.json.return_value = {
            "data": {
                "organization": {
                    "teams": {
                        "nodes": [
                            {
                                "slug": "team-alpha",
                                "name": "Team Alpha",
                                "members": {
                                    "nodes": [
                                        {
                                            "login": "member1",
                                            "email": "member1@example.com",
                                        }
                                    ],
                                    "pageInfo": {
                                        "hasNextPage": False,
                                        "endCursor": None,
                                    },
                                },
                            }
                        ],
                        "pageInfo": {"hasNextPage": True, "endCursor": "parent_cursor"},
                    }
                }
            }
        }

        # Second parent page
        second_response = MagicMock(spec=Response)
        second_response.status_code = 200
        second_response.json.return_value = {
            "data": {
                "organization": {
                    "teams": {
                        "nodes": [
                            {
                                "slug": "team-beta",
                                "name": "Team Beta",
                                "members": {
                                    "nodes": [
                                        {
                                            "login": "member2",
                                            "email": "member2@example.com",
                                        }
                                    ],
                                    "pageInfo": {
                                        "hasNextPage": False,
                                        "endCursor": None,
                                    },
                                },
                            }
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }

        nested_config = {
            "parent_path": "organization.teams",
            "child_path": "members",
            "parent_page_size": 1,  # Small page size to force multiple pages
            "child_page_size": 50,
        }

        with patch.object(
            graphql_client,
            "send_api_request",
            AsyncMock(side_effect=[first_response, second_response]),
        ):
            results = []
            async for page in graphql_client.send_nested_paginated_request(
                "query",
                params={"organization": "test-org"},
                nested_config=nested_config,
            ):
                results.append(page)

            assert len(results) == 2

            # First page
            assert len(results[0]) == 1
            assert results[0][0]["slug"] == "team-alpha"

            # Second page
            assert len(results[1]) == 1
            assert results[1][0]["slug"] == "team-beta"

    async def test_extract_nested_data(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test extracting nested data from parent node."""
        parent_node = {
            "slug": "team-alpha",
            "members": {
                "nodes": [{"login": "member1"}],
                "pageInfo": {"hasNextPage": False},
            },
        }

        nested_data = graphql_client._extract_nested_data(parent_node, "members")
        assert nested_data == parent_node["members"]

        # Test with missing nested data
        nested_data = graphql_client._extract_nested_data(parent_node, "repositories")
        assert nested_data is None

    async def test_extract_single_parent_from_response(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test extracting single parent from different response structures."""
        # Test organization.team response
        team_response = {
            "organization": {"team": {"slug": "team-alpha", "name": "Team Alpha"}}
        }
        parent = graphql_client._extract_single_parent_from_response(team_response, {})
        assert parent == {"slug": "team-alpha", "name": "Team Alpha"}

        # Test organization.teams response with single item
        teams_response = {
            "organization": {
                "teams": {"nodes": [{"slug": "team-beta", "name": "Team Beta"}]}
            }
        }
        parent = graphql_client._extract_single_parent_from_response(teams_response, {})
        assert parent == {"slug": "team-beta", "name": "Team Beta"}

    async def test_cleanup_nested_response(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test cleaning up nested response by removing pageInfo."""
        parent_node = {
            "slug": "team-alpha",
            "members": {
                "nodes": [{"login": "member1"}],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            },
        }

        graphql_client._cleanup_nested_response(parent_node, "members")
        assert "pageInfo" not in parent_node["members"]

    async def test_update_nested_data(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        """Test updating nested data in parent node."""
        parent_node = {
            "slug": "team-alpha",
            "members": {
                "nodes": [{"login": "member1"}],
                "pageInfo": {"hasNextPage": False},
            },
        }

        new_nodes = [
            {"login": "member1", "email": "member1@example.com"},
            {"login": "member2", "email": "member2@example.com"},
        ]

        graphql_client._update_nested_data(parent_node, "members", new_nodes)
        assert parent_node["members"] == {"nodes": new_nodes}
