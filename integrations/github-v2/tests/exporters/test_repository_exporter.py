from typing import Any, AsyncGenerator
import pytest
from unittest.mock import patch, MagicMock
import httpx
from github.core.exporters.repository_exporter import RepositoryExporter
from github.clients.base_client import AbstractGithubClient
from github.utils import RepositoryType
from port_ocean.context.event import event_context
from github.core.options import SingleRepositoryOptions, ListRepositoryOptions


TEST_REPOS = [
    {"id": 1, "name": "repo1", "full_name": "test-org/repo1"},
    {"id": 2, "name": "repo2", "full_name": "test-org/repo2"},
]


@pytest.mark.asyncio
class TestRepositoryExporter:

    async def test_get_resource(self, client: AbstractGithubClient) -> None:
        # Create a mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = TEST_REPOS[0]

        exporter = RepositoryExporter(client)

        with patch.object(
            client, "send_api_request", return_value=mock_response
        ) as mock_request:
            repo = await exporter.get_resource(SingleRepositoryOptions(name="repo1"))

            assert repo == TEST_REPOS[0]

            mock_request.assert_called_once_with(f"repos/{client.organization}/repo1")

    async def test_get_paginated_resources(self, client: AbstractGithubClient) -> None:
        options = ListRepositoryOptions(type=RepositoryType.ALL)
        exporter = RepositoryExporter(client)

        # Create an async mock to return the test repos
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_REPOS

        with patch.object(
            client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:

            async with event_context("test_event"):
                repos: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(repos) == 1
                assert len(repos[0]) == 2
                assert repos[0] == TEST_REPOS

            mock_request.assert_called_once_with(
                f"orgs/{client.organization}/repos", {"type": RepositoryType.ALL}
            )
