from typing import Any, AsyncGenerator
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from github.core.exporters.branch_exporter import RestBranchExporter
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context
from github.core.options import SingleBranchOptions, ListBranchOptions
from github.clients.http.rest_client import GithubRestClient


TEST_BRANCHES = [
    {
        "name": "main",
        "commit": {
            "sha": "abc123",
            "url": "https://api.github.com/repos/test-org/repo1/commits/abc123",
        },
        "protected": True,
    },
    {
        "name": "develop",
        "commit": {
            "sha": "def456",
            "url": "https://api.github.com/repos/test-org/repo1/commits/def456",
        },
        "protected": False,
    },
]


@pytest.mark.asyncio
class TestRestBranchExporter:
    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        # Create a mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = TEST_BRANCHES[0]

        exporter = RestBranchExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response.json()
            branch = await exporter.get_resource(
                SingleBranchOptions(repo_name="repo1", branch_name="main")
            )

            assert branch["__repository"] == "repo1"  # Check repository is enriched
            assert branch["name"] == "main"  # Check name is preserved

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/repo1/branches/main"
            )

    async def test_get_paginated_resources(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        # Create an async mock to return the test branches
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_BRANCHES

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListBranchOptions(repo_name="repo1")
                exporter = RestBranchExporter(rest_client)

                branches: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(branches) == 1
                assert len(branches[0]) == 2

                # Check each branch is properly enriched
                for branch in branches[0]:
                    assert "__repository" in branch

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/repos/{rest_client.organization}/repo1/branches",
                    {},
                )
