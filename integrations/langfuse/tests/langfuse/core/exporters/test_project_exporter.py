from unittest.mock import AsyncMock, MagicMock

import pytest

from langfuse.core.exporters.project_exporter import ProjectExporter

PROJECT = {
    "id": "clxxxx",
    "name": "My Project",
    "metadata": {},
    "organization": {"id": "org", "name": "Org"},
}


@pytest.mark.asyncio
class TestProjectExporter:
    async def test_get_resource(self) -> None:
        mock_client = MagicMock()
        mock_client.send_api_request = AsyncMock(return_value={"data": [PROJECT]})
        exporter = ProjectExporter(mock_client)
        assert await exporter.get_resource() == PROJECT

    async def test_get_paginated_resources(self) -> None:
        mock_client = MagicMock()
        mock_client.send_api_request = AsyncMock(return_value={"data": [PROJECT]})
        exporter = ProjectExporter(mock_client)
        batches = [b async for b in exporter.get_paginated_resources()]
        assert batches == [[PROJECT]]
