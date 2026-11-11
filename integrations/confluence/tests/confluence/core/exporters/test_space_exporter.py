from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest

from confluence.core.exporters.space_exporter import SpaceExporter
from confluence.core.options import SpaceExportOptions


def _client() -> tuple[MagicMock, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []

    async def paginate(
        endpoint: str, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        calls.append({"endpoint": endpoint, "params": params})
        yield [{"id": "1", "key": "DOCS", "_links": {"webui": "/spaces/DOCS"}}]

    client = MagicMock()
    client.site_url = "https://example.atlassian.net"
    client.send_paginated_request = paginate
    client.send_api_request = AsyncMock(return_value={})
    return client, calls


@pytest.mark.asyncio
class TestSpaceExporter:
    async def test_default_sync_requests_every_space(self) -> None:
        client, calls = _client()
        exporter = SpaceExporter(client)

        batches = [batch async for batch in exporter.get_paginated_resources()]

        assert calls == [
            {"endpoint": "spaces", "params": {"description-format": "plain"}},
        ]
        assert (
            batches[0][0]["webUrl"] == "https://example.atlassian.net/wiki/spaces/DOCS"
        )

    async def test_selector_filters_are_forwarded(self) -> None:
        client, calls = _client()
        exporter = SpaceExporter(client)

        _ = [
            batch
            async for batch in exporter.get_paginated_resources(
                SpaceExportOptions(
                    space_type="global",
                    status="current",
                    labels=["docs", "public"],
                )
            )
        ]

        assert calls[0]["params"] == {
            "description-format": "plain",
            "type": "global",
            "status": "current",
            "labels": "docs,public",
        }

    async def test_get_single_resource(self) -> None:
        client, _calls = _client()
        client.send_api_request = AsyncMock(
            return_value={
                "id": "123",
                "key": "DOCS",
                "_links": {"webui": "/spaces/DOCS"},
            }
        )
        exporter = SpaceExporter(client)

        result = await exporter.get_single_resource("123")

        assert result is not None
        assert result["webUrl"] == "https://example.atlassian.net/wiki/spaces/DOCS"
        client.send_api_request.assert_awaited_once_with(
            "spaces/123",
            params={"description-format": "plain"},
            missing_ok=True,
        )

    async def test_get_single_resource_not_found(self) -> None:
        client, _calls = _client()
        exporter = SpaceExporter(client)

        assert await exporter.get_single_resource("404") is None
