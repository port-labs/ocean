from typing import Any, AsyncGenerator
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from github.core.exporters.deployment_status_exporter import (
    RestDeploymentStatusExporter,
)
from github.core.options import (
    SingleDeploymentStatusOptions,
    ListDeploymentStatusesOptions,
)
from github.clients.http.rest_client import GithubRestClient
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context


TEST_DEPLOYMENT_STATUSES = [
    {
        "id": 456,
        "state": "success",
        "description": "Deployment finished successfully",
        "environment": "production",
        "log_url": "https://github.com/org/repo/actions/runs/123/job/456",
        "environment_url": "https://production.example.com",
        "created_at": "2024-03-20T10:05:00Z",
        "updated_at": "2024-03-20T10:05:00Z",
    },
    {
        "id": 457,
        "state": "pending",
        "description": "Deployment in progress",
        "environment": "production",
        "log_url": "https://github.com/org/repo/actions/runs/123/job/457",
        "environment_url": None,
        "created_at": "2024-03-20T10:00:00Z",
        "updated_at": "2024-03-20T10:00:00Z",
    },
]


@pytest.mark.asyncio
class TestRestDeploymentStatusExporter:
    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        """Test fetching a single deployment status."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = TEST_DEPLOYMENT_STATUSES[0]

        exporter = RestDeploymentStatusExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response.json()
            status = await exporter.get_resource(
                SingleDeploymentStatusOptions(
                    organization="test-org",
                    repo_name="test-repo",
                    deployment_id="123",
                    status_id="456",
                )
            )

            assert status == {
                **TEST_DEPLOYMENT_STATUSES[0],
                "__repository": "test-repo",
                "__organization": "test-org",
                "__deployment_id": "123",
            }

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/test-org/test-repo/deployments/123/statuses/456"
            )

    async def test_get_resource_not_found(self, rest_client: GithubRestClient) -> None:
        """Test fetching a deployment status that doesn't exist."""
        exporter = RestDeploymentStatusExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = None
            status = await exporter.get_resource(
                SingleDeploymentStatusOptions(
                    organization="test-org",
                    repo_name="test-repo",
                    deployment_id="123",
                    status_id="999",
                )
            )

            assert status is None

    async def test_get_paginated_resources(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        """Test fetching paginated deployment statuses."""

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_DEPLOYMENT_STATUSES

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListDeploymentStatusesOptions(
                    organization="test-org",
                    repo_name="test-repo",
                    deployment_id="123",
                )
                exporter = RestDeploymentStatusExporter(rest_client)

                statuses: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(statuses) == 1
                assert len(statuses[0]) == 2

                for status in statuses[0]:
                    assert status["__repository"] == "test-repo"
                    assert status["__organization"] == "test-org"
                    assert status["__deployment_id"] == "123"

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/repos/test-org/test-repo/deployments/123/statuses",
                )

    async def test_get_paginated_resources_empty(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        """Test fetching paginated deployment statuses when none exist."""

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield []

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ):
            async with event_context("test_event"):
                options = ListDeploymentStatusesOptions(
                    organization="test-org",
                    repo_name="test-repo",
                    deployment_id="123",
                )
                exporter = RestDeploymentStatusExporter(rest_client)

                statuses: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(statuses) == 1
                assert len(statuses[0]) == 0
