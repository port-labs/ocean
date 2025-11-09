import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.clients.http.graphql_client import GithubGraphQLClient
from github.helpers.exceptions import GraphQLClientError, GraphQLErrorGroup


@pytest.mark.asyncio
class TestGithubGraphQLClient:
    def test_graphql_base_url_github_com(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )
        assert client.base_url == "https://api.github.com/graphql"

    def test_graphql_base_url_ghe_api_v3(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://ghe.example.com/api/v3",
            authenticator=authenticator,
        )
        assert client.base_url == "https://ghe.example.com/api/graphql"

    async def test_handle_graphql_errors(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # Mock response with GraphQL errors
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {}  # Add headers attribute
        mock_response.json.return_value = {
            "errors": [
                {"message": "Error 1", "path": ["field1"], "type": "CUSTOM_ERROR_1"},
                {"message": "Error 2", "path": ["field2"], "type": "CUSTOM_ERROR_2"},
            ]
        }

        # Mock the client's configuration
        mock_config = MagicMock()
        mock_config.client_timeout = 30.0  # Set a proper float value for timeout

        with patch(
            "port_ocean.helpers.async_client.OceanAsyncClient.request",
            AsyncMock(return_value=mock_response),
        ):
            with pytest.raises(GraphQLErrorGroup) as exc_info:
                await client.send_api_request(
                    client.base_url, method="POST", json_data={}
                )

            # Verify the exception group
            assert (
                str(exc_info.value) == "GraphQL errors occurred:\n- Error 1\n- Error 2"
            )
            assert len(exc_info.value.errors) == 2
            assert str(exc_info.value.errors[0]) == "Error 1"
            assert str(exc_info.value.errors[1]) == "Error 2"

    async def test_handle_graphql_success(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # Mock successful response
        mock_response_data = {
            "data": {
                "organization": {
                    "repositories": {
                        "nodes": [{"id": 1, "name": "repo1"}],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }

        with patch.object(
            client, "send_api_request", AsyncMock(return_value=mock_response_data)
        ):
            response = await client.send_api_request(
                client.base_url, method="POST", json_data={}
            )
            assert response["data"]["organization"]["repositories"]["nodes"] == [
                {"id": 1, "name": "repo1"}
            ]

    async def test_send_paginated_request_single_page(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # Mock response with no next page
        mock_response_data = {
            "data": {
                "organization": {
                    "repositories": {
                        "nodes": [{"id": 1, "name": "repo1"}],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }

        with patch.object(
            client, "send_api_request", AsyncMock(return_value=mock_response_data)
        ):
            results = []
            async for page in client.send_paginated_request(
                "query", params={"__path": "organization.repositories"}
            ):
                results.append(page)

            assert len(results) == 1
            assert results[0] == [{"id": 1, "name": "repo1"}]

    async def test_send_paginated_request_multiple_pages(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # First response with next page

        first_response_data = {
            "data": {
                "organization": {
                    "repositories": {
                        "nodes": [{"id": 1, "name": "repo1"}],
                        "pageInfo": {"hasNextPage": True, "endCursor": "cursor1"},
                    }
                }
            }
        }

        # Second response with no next page

        second_response_data = {
            "data": {
                "organization": {
                    "repositories": {
                        "nodes": [{"id": 2, "name": "repo2"}],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }

        with patch.object(
            client,
            "send_api_request",
            AsyncMock(side_effect=[first_response_data, second_response_data]),
        ):
            results = []
            async for page in client.send_paginated_request(
                "query", params={"__path": "organization.repositories"}
            ):
                results.append(page)

            assert len(results) == 2
            assert results[0] == [{"id": 1, "name": "repo1"}]
            assert results[1] == [{"id": 2, "name": "repo2"}]

    async def test_send_paginated_request_empty_response(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # Mock response with empty nodes
        mock_response_data = {
            "data": {
                "organization": {
                    "repositories": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }

        with patch.object(
            client, "send_api_request", AsyncMock(return_value=mock_response_data)
        ):
            results = []
            async for page in client.send_paginated_request(
                "query", params={"__path": "organization.repositories"}
            ):
                results.append(page)

            assert len(results) == 0

    async def test_send_paginated_request_missing_path(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubGraphQLClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        with pytest.raises(
            GraphQLClientError, match="GraphQL pagination requires a '__path'"
        ):
            async for _ in client.send_paginated_request("query"):
                pass
