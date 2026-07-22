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

TEST_VARIABLES = [
    {
        "name": "APP_URL",
        "value": "https://example.com",
        "created_at": "2024-03-20T10:00:00Z",
        "updated_at": "2024-03-20T10:00:00Z",
    },
    {
        "name": "DEPLOY_TIMEOUT",
        "value": "300",
        "created_at": "2024-03-20T10:00:00Z",
        "updated_at": "2024-03-20T10:00:00Z",
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
                SingleEnvironmentOptions(
                    organization="test-org", repo_name="test-repo", name="production"
                )
            )

            assert environment == {
                **TEST_ENVIRONMENTS[0],
                "__repository": "test-repo",
                "__organization": "test-org",
            }

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/test-org/test-repo/environments/production"
            )

    async def test_get_resource_with_variables(
        self, rest_client: GithubRestClient
    ) -> None:
        """variables=True fetches and attaches __variables to the environment."""
        exporter = RestEnvironmentExporter(rest_client)

        async def mock_paginated_variables(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[dict[str, Any], None]:
            yield {"variables": TEST_VARIABLES}

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_api, patch.object(
            rest_client,
            "send_paginated_request",
            side_effect=mock_paginated_variables,
        ):
            mock_api.return_value = TEST_ENVIRONMENTS[0]
            environment = await exporter.get_resource(
                SingleEnvironmentOptions(
                    organization="test-org",
                    repo_name="test-repo",
                    name="production",
                    include_variables=True,
                )
            )

            assert environment["__variables"] == TEST_VARIABLES
            assert environment["__repository"] == "test-repo"

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
                options = ListEnvironmentsOptions(
                    organization="test-org", repo_name="test-repo"
                )
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
                assert all(
                    environment["__organization"] == "test-org"
                    for environment in environments[0]
                )

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/repos/test-org/test-repo/environments",
                    {},
                )

    async def test_get_paginated_resources_with_variables(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        """variables=True enriches each environment in the batch with __variables."""
        exporter = RestEnvironmentExporter(rest_client)

        call_count = 0

        async def mock_paginated(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[dict[str, Any], None]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: environments list
                yield {"environments": TEST_ENVIRONMENTS}
            else:
                # Subsequent calls: variables for each environment
                yield {"variables": TEST_VARIABLES}

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated
        ):
            async with event_context("test_event"):
                options = ListEnvironmentsOptions(
                    organization="test-org",
                    repo_name="test-repo",
                    include_variables=True,
                )
                environments: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(environments) == 1
                assert all(
                    environment["__variables"] == TEST_VARIABLES
                    for environment in environments[0]
                )
