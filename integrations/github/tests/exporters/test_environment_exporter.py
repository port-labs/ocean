from typing import Any, AsyncGenerator
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from github.core.exporters.environment_exporter import RestEnvironmentExporter
from github.core.options import SingleEnvironmentOptions, ListEnvironmentsOptions
from github.clients.http.rest_client import GithubRestClient
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context


TEST_ENVIRONMENTS = [
    {
        "name": "production",
        "url": "https://github.com/org/repo/environments/production",
        "created_at": "2024-03-20T10:00:00Z",
        "updated_at": "2024-03-20T10:00:00Z",
        "protected_branches": True,
        "custom_branch_policies": True,
    },
    {
        "name": "staging",
        "url": "https://github.com/org/repo/environments/staging",
        "created_at": "2024-03-20T10:00:00Z",
        "updated_at": "2024-03-20T10:00:00Z",
        "protected_branches": True,
        "custom_branch_policies": False,
    },
]


@pytest.mark.asyncio
class TestRestEnvironmentExporter:
    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        # Create a mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = TEST_ENVIRONMENTS[0]

        exporter = RestEnvironmentExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response.json()
            environment = await exporter.get_resource(
                SingleEnvironmentOptions(repo_name="test-repo", name="production")
            )

            assert environment == {**TEST_ENVIRONMENTS[0], "__repository": "test-repo"}

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/test-repo/environments/production"
            )

    async def test_get_paginated_resources(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        # Create an async mock to return the test environments
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[dict[str, Any], None]:
            yield {"environments": TEST_ENVIRONMENTS}

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListEnvironmentsOptions(repo_name="test-repo")
                exporter = RestEnvironmentExporter(rest_client)

                environments: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(environments) == 1
                assert len(environments[0]) == 2
                assert all(
                    "__repository" in environment for environment in environments[0]
                )
                assert all(
                    environment["__repository"] == "test-repo"
                    for environment in environments[0]
                )

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/repos/{rest_client.organization}/test-repo/environments",
                    {},
                )
