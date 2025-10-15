from typing import Any, AsyncGenerator
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from github.core.exporters.tag_exporter import RestTagExporter
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context
from github.core.options import SingleTagOptions, ListTagOptions
from github.clients.http.rest_client import GithubRestClient


TEST_TAGS = [
    {
        "ref": "refs/tags/v1.0",
        "object": {
            "sha": "abc123",
            "type": "commit",
            "url": "https://api.github.com/repos/test-org/repo1/git/commits/abc123",
        },
    },
    {
        "ref": "refs/tags/v2.0",
        "object": {
            "sha": "def456",
            "type": "commit",
            "url": "https://api.github.com/repos/test-org/repo1/git/commits/def456",
        },
    },
]


@pytest.mark.asyncio
class TestRestTagExporter:
    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        # Create a mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = TEST_TAGS[0]

        exporter = RestTagExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response.json()
            tag = await exporter.get_resource(
                SingleTagOptions(repo_name="repo1", tag_name="v1.0")
            )

            assert tag["name"] == "v1.0"  # Check name is set
            assert tag["__repository"] == "repo1"  # Check repository is enriched
            assert tag["commit"] == TEST_TAGS[0]["object"]  # Check commit is set

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/repo1/git/refs/tags/v1.0"
            )

    async def test_get_paginated_resources(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        # Create an async mock to return the test tags
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_TAGS

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListTagOptions(repo_name="repo1")
                exporter = RestTagExporter(rest_client)

                tags: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(tags) == 1
                assert len(tags[0]) == 2

                # Check each tag is properly enriched
                for tag in tags[0]:
                    assert "__repository" in tag

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/repos/{rest_client.organization}/repo1/tags",
                    {},
                )
