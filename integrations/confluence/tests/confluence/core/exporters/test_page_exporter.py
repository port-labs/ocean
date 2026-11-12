from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest

from confluence.core.exporters.page_exporter import (
    BODY_PAGE_SIZE,
    METADATA_PAGE_SIZE,
    PageExporter,
)
from confluence.core.options import PageExportOptions


def _pages(
    pages: list[dict[str, Any]],
) -> Any:
    async def paginate(
        endpoint: str, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        yield pages

    return paginate


def _client() -> tuple[MagicMock, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []

    async def paginate(
        endpoint: str, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        calls.append({"endpoint": endpoint, "params": params})
        yield [
            {
                "id": "9",
                "title": "Getting Started",
                "spaceId": "1",
                "_links": {"webui": "/spaces/DOCS/pages/9/Getting+Started"},
            }
        ]

    client = MagicMock()
    client.site_url = "https://example.atlassian.net"
    client.send_paginated_request = paginate
    client.send_api_request = AsyncMock(return_value={})
    return client, calls


@pytest.mark.asyncio
class TestPageExporter:
    async def test_default_sync_requests_current_pages_with_markdown(self) -> None:
        client, calls = _client()
        exporter = PageExporter(client)

        batches = [
            batch
            async for batch in exporter.get_paginated_resources(PageExportOptions())
        ]

        assert calls == [
            {
                "endpoint": "pages",
                "params": {"status": ["current"], "limit": METADATA_PAGE_SIZE},
            },
            {
                "endpoint": "pages",
                "params": {
                    "status": ["current"],
                    "body-format": "markdown",
                    "limit": BODY_PAGE_SIZE,
                },
            },
        ]
        page = batches[0][0]
        assert page["spaceId"] == "1"
        assert page["__webUrl"].endswith("/wiki/spaces/DOCS/pages/9/Getting+Started")
        assert page["__folderPath"] == "DOCS"
        assert page["__filePath"] == "DOCS/Getting Started.md"

    async def test_include_archived_and_body(self) -> None:
        client, calls = _client()
        exporter = PageExporter(client)

        _ = [
            batch
            async for batch in exporter.get_paginated_resources(
                PageExportOptions(include_archived=True, include_body=True)
            )
        ]

        assert calls[0]["params"]["status"] == ["current", "archived"]
        assert calls[0]["params"]["limit"] == METADATA_PAGE_SIZE
        assert calls[1]["params"]["body-format"] == "markdown"
        assert calls[1]["params"]["limit"] == BODY_PAGE_SIZE

    async def test_space_ids_are_forwarded(self) -> None:
        client, calls = _client()
        exporter = PageExporter(client)

        _ = [
            batch
            async for batch in exporter.get_paginated_resources(
                PageExportOptions(space_ids=["98316", "622596"])
            )
        ]

        assert calls[0]["params"]["space-id"] == ["98316", "622596"]

    async def test_whiteboard_and_database_parents_are_included_in_the_path(
        self,
    ) -> None:
        client = MagicMock()
        client.site_url = "https://example.atlassian.net"
        client.send_paginated_request = _pages(
            [
                {
                    "id": "page-1",
                    "title": "Install",
                    "spaceId": "1",
                    "parentId": "db-1",
                    "parentType": "database",
                    "_links": {"webui": "/spaces/DOCS/pages/page-1/Install"},
                }
            ]
        )
        client.send_api_request = AsyncMock(
            side_effect=lambda endpoint, **kwargs: {
                "databases/db-1": {
                    "id": "db-1",
                    "title": "Tracking",
                    "parentId": "wb-1",
                    "parentType": "whiteboard",
                },
                "whiteboards/wb-1": {
                    "id": "wb-1",
                    "title": "Sketch",
                    "parentId": "folder-1",
                    "parentType": "folder",
                },
                "folders/folder-1": {
                    "id": "folder-1",
                    "title": "Engineering",
                    "parentId": None,
                    "parentType": None,
                },
            }.get(endpoint, {})
        )
        exporter = PageExporter(client)

        batches = [
            batch
            async for batch in exporter.get_paginated_resources(
                PageExportOptions(include_body=False)
            )
        ]

        page = batches[0][0]
        assert page["__folderPath"] == "DOCS/Engineering/Sketch/Tracking"
        assert page["__filePath"] == "DOCS/Engineering/Sketch/Tracking/Install.md"
        requested = {call.args[0] for call in client.send_api_request.await_args_list}
        assert requested == {
            "databases/db-1",
            "whiteboards/wb-1",
            "folders/folder-1",
        }

    async def test_get_single_resource_not_found(self) -> None:
        client, _calls = _client()
        exporter = PageExporter(client)

        assert await exporter.get_single_resource("15") is None
