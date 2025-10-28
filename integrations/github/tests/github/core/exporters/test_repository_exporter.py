from typing import Any, AsyncGenerator
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from github.core.exporters.repository_exporter import (
    RestRepositoryExporter,
)
from github.core.options import ListRepositoryOptions, SingleRepositoryOptions
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context
from github.helpers.models import RepoSearchParams
from github.clients.http.rest_client import GithubRestClient


TEST_REPOS = [
    {
        "id": 1,
        "name": "repo1",
        "full_name": "test-org/repo1",
        "description": "Test repository 1",
    },
    {
        "id": 2,
        "name": "repo2",
        "full_name": "test-org/repo2",
        "description": "Test repository 2",
    },
]

TEST_COLLABORATORS = [
    {
        "id": 101,
        "login": "user1",
        "type": "User",
    },
    {
        "id": 102,
        "login": "user2",
        "type": "User",
    },
]


@pytest.mark.asyncio
class TestRestRepositoryExporter:
    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        # Create a mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = TEST_REPOS[0]

        exporter = RestRepositoryExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response.json()
            repo = await exporter.get_resource(
                SingleRepositoryOptions(organization="test-org", name="repo1")
            )

            assert repo == TEST_REPOS[0]

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/test-org/repo1"
            )

    async def test_get_paginated_resources(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        # Create an async mock to return the test repos
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_REPOS

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListRepositoryOptions(
                    organization="test-org",
                    type=mock_port_app_config.repository_type,
                )
                exporter = RestRepositoryExporter(rest_client)

                repos: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(repos) == 1
                assert len(repos[0]) == 2
                assert repos[0] == TEST_REPOS

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/orgs/test-org/repos",
                    {"type": "all"},
                )

    async def test_get_paginated_resources_with_included_relationships(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        # Create a mock that returns different data based on the URL
        async def mock_paginated_request(
            url: str, *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            if "collaborators" in url:
                yield TEST_COLLABORATORS
            else:
                yield TEST_REPOS

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListRepositoryOptions(
                    organization="test-org",
                    type=mock_port_app_config.repository_type,
                    included_relationships=["collaborators"],
                )
                exporter = RestRepositoryExporter(rest_client)

                repos: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(repos) == 1
                assert len(repos[0]) == 2

                # Verify that repositories are enriched with collaborators
                for repo in repos[0]:
                    assert "__collaborators" in repo
                    assert repo["__collaborators"] == TEST_COLLABORATORS
                    # Verify original repository data is preserved
                    assert "id" in repo
                    assert "name" in repo
                    assert "full_name" in repo
                    assert "description" in repo

                # Verify the main repository request was called
                mock_request.assert_any_call(
                    f"{rest_client.base_url}/orgs/test-org/repos",
                    {"type": "all", "included_relationships": ["collaborators"]},
                )

                # Verify collaborator requests were called for each repository
                expected_collaborator_calls: list[tuple[str, dict[str, Any]]] = [
                    (
                        f"{rest_client.base_url}/repos/test-org/repo1/collaborators",
                        {},
                    ),
                    (
                        f"{rest_client.base_url}/repos/test-org/repo2/collaborators",
                        {},
                    ),
                ]

                # Should have 3 total calls: 1 for repositories + 2 for collaborators
                assert mock_request.call_count == 3
                mock_request.assert_any_call(*expected_collaborator_calls[0])
                mock_request.assert_any_call(*expected_collaborator_calls[1])

    async def test_get_paginated_resources_with_search_params(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        async def mock_paginated_request(
            url: str, params: dict[str, Any], *args: Any, **kwargs: Any
        ) -> AsyncGenerator[dict[str, Any] | list[dict[str, Any]], None]:
            if "search" in url:
                yield {"items": TEST_REPOS}
            else:
                yield TEST_REPOS

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListRepositoryOptions(
                    organization="test-org",
                    type=mock_port_app_config.repository_type,
                    search_params=RepoSearchParams(
                        operators={"archived": "false", "fork": "true"}
                    ),
                )
                exporter = RestRepositoryExporter(rest_client)

                repos: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(repos) == 1
                assert len(repos[0]) == 2
                assert repos[0] == TEST_REPOS

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/search/repositories",
                    {
                        "q": "org:test-org archived:false fork:true",
                        "type": "all",
                    },
                )
