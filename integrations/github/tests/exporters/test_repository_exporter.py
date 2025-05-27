from typing import Any
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from github.core.exporters.repository_exporter import (
    RestRepositoryExporter,
)
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context
from github.core.options import SingleRepositoryOptions, ListRepositoryOptions
from github.clients.rest_client import GithubRestClient


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


@pytest.fixture
def mock_port_app_config() -> GithubPortAppConfig:
    return GithubPortAppConfig(
        delete_dependent_entities=True,
        create_missing_related_entities=False,
        repository_visibility_filter="all",
        resources=[
            ResourceConfig(
                kind="repository",
                selector=Selector(query="true"),
                port=PortResourceConfig(
                    entity=MappingsConfig(
                        mappings=EntityMapping(
                            identifier=".full_name",
                            title=".name",
                            blueprint='"githubRepository"',
                            properties={},
                        )
                    )
                ),
            )
        ],
    )


@pytest.mark.asyncio
class TestRestRepositoryExporter:

    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        # Create a mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = TEST_REPOS[0]

        exporter = RestRepositoryExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", return_value=mock_response
        ) as mock_request:
            repo = await exporter.get_resource(SingleRepositoryOptions(name="repo1"))

            assert repo == TEST_REPOS[0]

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/repo1"
            )

    async def test_get_paginated_resources(
        self,
        rest_client: GithubRestClient,
        mock_port_app_config: GithubPortAppConfig,
        mock_event_context: MagicMock,
    ) -> None:

        with patch.object(
            rest_client,
            "send_api_request",
            AsyncMock(return_value=httpx.Response(json=TEST_REPOS, status_code=200)),
        ) as mock_request:
            async with event_context("test_event"):
                options = ListRepositoryOptions(
                    type=mock_port_app_config.repository_visibility_filter
                )
                exporter = RestRepositoryExporter(rest_client)

                repos: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(repos) == 1
                assert len(repos[0]) == 2
                assert repos[0] == TEST_REPOS

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/orgs/{rest_client.organization}/repos",
                    method="GET",
                    params={"type": "all", "per_page": 100},
                )
