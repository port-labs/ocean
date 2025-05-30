from typing import Any, AsyncGenerator
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.folder_exporter import (
    RestFolderExporter,
)
from integration import GithubPortAppConfig
from port_ocean.context.event import event_context
from github.core.options import SingleFolderOptions, ListFolderOptions


TEST_FILE = {
    "name": "README.md",
    "path": "README.md",
    "type": "file",
    "size": 123,
    "url": "https://api.github.com/repos/test-org/test-repo/contents/README.md",
}

TEST_DIR_1 = {
    "name": "src",
    "path": "src",
    "type": "dir",
    "size": 0,
    "url": "https://api.github.com/repos/test-org/test-repo/contents/src",
}

TEST_DIR_2 = {
    "name": "docs",
    "path": "docs",
    "type": "dir",
    "size": 0,
    "url": "https://api.github.com/repos/test-org/test-repo/contents/docs",
}

TEST_FOLDERS = [TEST_DIR_1, TEST_DIR_2]
TEST_FULL_CONTENTS = [TEST_DIR_1, TEST_FILE, TEST_DIR_2]


@pytest.mark.asyncio
class TestRestFolderExporter:
    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        # Create a mock response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = TEST_FILE

        exporter = RestFolderExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response.json()
            item = await exporter.get_resource(
                SingleFolderOptions(repo="test-repo", path="README.md")
            )

            assert item == TEST_FILE

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/test-repo/contents/README.md"
            )

    async def test_get_paginated_resources(
        self, rest_client: GithubRestClient, mock_port_app_config: GithubPortAppConfig
    ) -> None:
        # Create an async mock to return the test folder contents (includes files and dirs)
        async def mock_paginated_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_FULL_CONTENTS

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            async with event_context("test_event"):
                options = ListFolderOptions(repo="test-repo", path="")
                exporter = RestFolderExporter(rest_client)

                folders: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(folders) == 1
                assert len(folders[0]) == 2
                assert folders[0] == TEST_FOLDERS

                mock_request.assert_called_once_with(
                    f"{rest_client.base_url}/repos/{rest_client.organization}/test-repo/contents/"
                )
