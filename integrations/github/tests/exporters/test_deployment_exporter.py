from typing import Any, AsyncGenerator
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from github.core.exporters.deployment_exporter import RestDeploymentExporter
from github.core.options import SingleDeploymentOptions, ListDeploymentsOptions
from github.clients.http.rest_client import GithubRestClient
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context


TEST_DEPLOYMENTS = [
    {
        "id": 123,
        "environment": "production",
        "ref": "main",
        "sha": "abc123",
        "description": "Deploy to production",
        "url": "https://github.com/org/repo/deployments/123",
        "created_at": "2024-03-20T10:00:00Z",
        "transient_environment": False,
        "production_environment": True,
    },
    {
        "id": 124,
        "environment": "production",
        "ref": "main",
        "sha": "def456",
        "description": "Deploy to production",
        "url": "https://github.com/org/repo/deployments/124",
        "created_at": "2024-03-20T11:00:00Z",
        "transient_environment": False,
        "production_environment": True,
    },
]


@pytest.mark.asyncio
class TestRestDeploymentExporter:
    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        # Create a mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = TEST_DEPLOYMENTS[0]

        exporter = RestDeploymentExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response.json()
            deployment = await exporter.get_resource(
                SingleDeploymentOptions(repo_name="test-repo", id="123")
            )

            assert deployment == {**TEST_DEPLOYMENTS[0], "__repository": "test-repo"}

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/test-repo/deployments/123"
            )

    async def test_get_paginated_resources(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        # Create an async mock to return the test deployments
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_DEPLOYMENTS

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListDeploymentsOptions(repo_name="test-repo")
                exporter = RestDeploymentExporter(rest_client)

                deployments: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(deployments) == 1
                assert len(deployments[0]) == 2
                assert all(
                    "__repository" in deployment for deployment in deployments[0]
                )
                assert all(
                    deployment["__repository"] == "test-repo"
                    for deployment in deployments[0]
                )

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/repos/{rest_client.organization}/test-repo/deployments",
                    {},
                )
