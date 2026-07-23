from datetime import datetime, timezone
from typing import Any, AsyncGenerator
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from github.core.exporters.release_exporter import RestReleaseExporter
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context
from github.core.options import SingleReleaseOptions, ListReleaseOptions
from github.clients.http.rest_client import GithubRestClient

TEST_RELEASES = [
    {
        "id": 1,
        "name": "Release 1.0",
        "tag_name": "v1.0",
        "body": "First release",
        "author": {"login": "user1"},
        "created_at": "2024-01-01T00:00:00Z",
    },
    {
        "id": 2,
        "name": "Release 2.0",
        "tag_name": "v2.0",
        "body": "Second release",
        "author": {"login": "user2"},
        "created_at": "2024-01-02T00:00:00Z",
    },
]


@pytest.mark.asyncio
class TestRestReleaseExporter:
    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        # Create a mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = TEST_RELEASES[0]

        exporter = RestReleaseExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response.json()
            release = await exporter.get_resource(
                SingleReleaseOptions(
                    organization="test-org", repo_name="repo1", release_id=1
                )
            )

            assert release is not None
            assert release["name"] == "Release 1.0"
            assert release["__repository"] == "repo1"  # Check repository is enriched

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/test-org/repo1/releases/1"
            )

    async def test_get_paginated_resources(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        # Create an async mock to return the test releases
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_RELEASES

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListReleaseOptions(organization="test-org", repo_name="repo1")
                exporter = RestReleaseExporter(rest_client)

                releases: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(releases) == 1
                assert len(releases[0]) == 2

                # Check each release is properly enriched
                for release in releases[0]:
                    assert "__repository" in release

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/repos/test-org/repo1/releases",
                    {},
                )

    async def test_get_paginated_resources_with_incremental_cursor_stops_at_old_items(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        cursor = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        mixed_releases = [
            {
                "id": 1,
                "name": "New release",
                "tag_name": "v2.0",
                "created_at": "2026-06-02T00:00:00Z",
            },
            {
                "id": 2,
                "name": "Old release",
                "tag_name": "v1.0",
                "created_at": "2026-05-01T00:00:00Z",
            },
        ]

        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield mixed_releases

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                exporter = RestReleaseExporter(rest_client)
                releases = [
                    batch
                    async for batch in exporter.get_paginated_resources(
                        ListReleaseOptions(
                            organization="test-org",
                            repo_name="repo1",
                            incremental_cursor=cursor,
                        )
                    )
                ]

            assert len(releases) == 1
            assert len(releases[0]) == 1
            assert releases[0][0]["tag_name"] == "v2.0"
            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/test-org/repo1/releases",
                {},
            )
