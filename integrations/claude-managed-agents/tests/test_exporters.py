from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import MagicMock

import pytest

from core.exporters.agents_exporter import AgentsExporter
from core.exporters.environments_exporter import EnvironmentsExporter
from core.exporters.memory_stores_exporter import MemoryStoresExporter
from core.exporters.sessions_exporter import SessionsExporter
from core.exporters.skills_exporter import SkillsExporter
from core.exporters.vaults_exporter import VaultsExporter


async def _batches(
    *pages: list[dict[str, Any]]
) -> AsyncGenerator[list[dict[str, Any]], None]:
    for page in pages:
        yield page


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exporter_cls, resource_name",
    [
        (AgentsExporter, "agents"),
        (EnvironmentsExporter, "environments"),
        (SessionsExporter, "sessions"),
        (VaultsExporter, "vaults"),
        (MemoryStoresExporter, "memory_stores"),
    ],
)
async def test_exporter_yields_batches(exporter_cls: type, resource_name: str) -> None:
    client = MagicMock()
    page = [{"id": "1"}, {"id": "2"}]
    client.paginate = MagicMock(return_value=_batches(page))

    exporter = exporter_cls(client)
    results = [batch async for batch in exporter.get_paginated_resources()]

    assert results == [page]
    getattr(client.beta, resource_name).list.assert_called_once_with(
        include_archived=False
    )
    client.paginate.assert_called_once_with(
        getattr(client.beta, resource_name).list.return_value
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exporter_cls, resource_name",
    [
        (AgentsExporter, "agents"),
        (EnvironmentsExporter, "environments"),
        (SessionsExporter, "sessions"),
        (VaultsExporter, "vaults"),
        (MemoryStoresExporter, "memory_stores"),
    ],
)
async def test_exporter_forwards_include_archived(
    exporter_cls: type, resource_name: str
) -> None:
    client = MagicMock()
    client.paginate = MagicMock(return_value=_batches())

    exporter = exporter_cls(client)
    [batch async for batch in exporter.get_paginated_resources(include_archived=True)]

    getattr(client.beta, resource_name).list.assert_called_once_with(
        include_archived=True
    )


@pytest.mark.asyncio
async def test_skills_exporter_yields_batches() -> None:
    client = MagicMock()
    page = [{"id": "1"}, {"id": "2"}]
    client.paginate = MagicMock(return_value=_batches(page))

    exporter = SkillsExporter(client)
    results = [batch async for batch in exporter.get_paginated_resources()]

    assert results == [page]
    client.beta.skills.list.assert_called_once_with(source="custom")
