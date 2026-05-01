from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.pages_exporter import RestPagesExporter
from github.core.options import ListPagesOptions, SinglePagesOptions
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
    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = TEST_PAGES

        exporter = RestPagesExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response.json().copy()
            pages = await exporter.get_resource(
                SinglePagesOptions(organization="test-org", repo_name="test-repo")
            )

            assert pages == {
                **TEST_PAGES,
                "__repository": "test-repo",
                "__organization": "test-org",
            }

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/test-org/test-repo/pages",
                {},
            )

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
        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
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

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/repos/test-org/test-repo/pages",
                    {},
                )
