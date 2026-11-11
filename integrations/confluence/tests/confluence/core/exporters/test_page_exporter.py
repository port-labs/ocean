from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest

from confluence.core.exporters.page_exporter import BODY_PAGE_SIZE, PageExporter
from confluence.core.options import PageExportOptions


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
                "params": {
                    "status": ["current"],
                    "body-format": "markdown",
                    "limit": BODY_PAGE_SIZE,
                },
            },
        ]
        assert batches[0][0]["spaceId"] == "1"
        assert batches[0][0]["webUrl"].endswith(
            "/wiki/spaces/DOCS/pages/9/Getting+Started"
        )

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
        assert calls[0]["params"]["body-format"] == "markdown"
        assert calls[0]["params"]["limit"] == BODY_PAGE_SIZE

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

    async def test_get_single_resource_not_found(self) -> None:
        client, _calls = _client()
        exporter = PageExporter(client)

        assert await exporter.get_single_resource("15") is None
