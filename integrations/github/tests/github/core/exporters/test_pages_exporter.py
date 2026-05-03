from unittest.mock import AsyncMock, patch

import pytest
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.pages_exporter import RestPagesExporter
from github.core.options import ListPagesOptions
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context

TEST_PAGES = {
    "url": "https://api.github.com/repos/test-org/test-repo/pages",
    "status": "built",
    "cname": "example.com",
    "custom_404": False,
    "html_url": "https://test-org.github.io/test-repo/",
    "source": {"branch": "main", "path": "/docs"},
    "public": True,
}


@pytest.mark.asyncio
class TestRestPagesExporter:
    async def test_get_paginated_resources(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = TEST_PAGES.copy()
            async with event_context("test_event"):
                options = ListPagesOptions(
                    organization="test-org", repo_name="test-repo"
                )
                exporter = RestPagesExporter(rest_client)

                pages: list[list[dict[str, object]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert pages == [
                    [
                        {
                            **TEST_PAGES,
                            "__repository": "test-repo",
                            "__organization": "test-org",
                        }
                    ]
                ]

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/repos/test-org/test-repo/pages",
                    {},
                )

    async def test_get_paginated_resources_skips_missing_pages(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        with (
            patch.object(
                rest_client, "send_api_request", new_callable=AsyncMock
            ) as mock_request,
            patch(
                "github.core.exporters.pages_exporter.logger.warning"
            ) as mock_warning,
        ):
            mock_request.return_value = {}
            async with event_context("test_event"):
                options = ListPagesOptions(
                    organization="test-org", repo_name="test-repo"
                )
                exporter = RestPagesExporter(rest_client)

                pages: list[list[dict[str, object]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert pages == []
                mock_warning.assert_not_called()

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/repos/test-org/test-repo/pages",
                    {},
                )
