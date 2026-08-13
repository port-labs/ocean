from typing import Any
from unittest.mock import MagicMock

import pytest

from mend.clients.client import MendClient
from mend.core.exporters.project_exporter import MendProjectExporter
from mend.core.options import ListProjectOptions


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock(spec=MendClient)
    client.org_uuid = "test-org-uuid"
    return client


@pytest.fixture
def exporter(mock_client: MagicMock) -> MendProjectExporter:
    return MendProjectExporter(mock_client)


class TestMendProjectExporter:
    @pytest.mark.asyncio
    async def test_get_paginated_resources_yields_projects(
        self, exporter: MendProjectExporter, mock_client: MagicMock
    ) -> None:
        projects = [
            {"uuid": "p1", "name": "Project A"},
            {"uuid": "p2", "name": "Project B"},
        ]

        async def fake_paginator(endpoint: str, method: str = "GET", json_data=None):  # type: ignore[no-untyped-def]
            yield projects

        mock_client.send_cursor_paginated_request = fake_paginator
        options = ListProjectOptions(org_uuid="test-org-uuid")
        results = []
        async for batch in exporter.get_paginated_resources(options):
            results.extend(batch)

        assert len(results) == 2
        assert results[0]["uuid"] == "p1"

    @pytest.mark.asyncio
    async def test_get_paginated_resources_uses_post(
        self, exporter: MendProjectExporter, mock_client: MagicMock
    ) -> None:
        called_with: dict[str, Any] = {}

        async def fake_paginator(endpoint: str, method: str = "GET", json_data=None):  # type: ignore[no-untyped-def]
            called_with["endpoint"] = endpoint
            called_with["method"] = method
            yield []

        mock_client.send_cursor_paginated_request = fake_paginator
        options = ListProjectOptions(org_uuid="my-org")
        async for _ in exporter.get_paginated_resources(options):
            pass

        assert called_with["method"] == "POST"
        assert "my-org" in called_with["endpoint"]

    @pytest.mark.asyncio
    async def test_get_paginated_resources_empty(
        self, exporter: MendProjectExporter, mock_client: MagicMock
    ) -> None:
        async def fake_paginator(endpoint: str, method: str = "GET", json_data=None):  # type: ignore[no-untyped-def]
            for _ in ():
                yield _

        mock_client.send_cursor_paginated_request = fake_paginator
        options = ListProjectOptions(org_uuid="test-org-uuid")
        results = []
        async for batch in exporter.get_paginated_resources(options):
            results.extend(batch)

        assert results == []
