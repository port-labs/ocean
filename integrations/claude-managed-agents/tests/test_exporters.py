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
    "exporter_cls, client_method",
    [
        (AgentsExporter, "get_agents"),
        (EnvironmentsExporter, "get_environments"),
        (SessionsExporter, "get_sessions"),
        (VaultsExporter, "get_vaults"),
        (MemoryStoresExporter, "get_memory_stores"),
    ],
)
async def test_exporter_yields_batches(exporter_cls: type, client_method: str) -> None:
    client = MagicMock()
    page = [{"id": "1"}, {"id": "2"}]
    setattr(client, client_method, lambda **_: _batches(page))

    exporter = exporter_cls(client)
    results = [batch async for batch in exporter.get_paginated_resources()]

    assert results == [page]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exporter_cls, client_method",
    [
        (AgentsExporter, "get_agents"),
        (EnvironmentsExporter, "get_environments"),
        (SessionsExporter, "get_sessions"),
        (VaultsExporter, "get_vaults"),
        (MemoryStoresExporter, "get_memory_stores"),
    ],
)
async def test_exporter_forwards_include_archived(
    exporter_cls: type, client_method: str
) -> None:
    client = MagicMock()
    calls: list[dict[str, Any]] = []

    def _record(**kwargs: Any) -> AsyncGenerator[list[dict[str, Any]], None]:
        calls.append(kwargs)
        return _batches([])

    setattr(client, client_method, _record)

    exporter = exporter_cls(client)
    [batch async for batch in exporter.get_paginated_resources(include_archived=True)]

    assert calls == [{"include_archived": True}]


@pytest.mark.asyncio
async def test_skills_exporter_yields_batches() -> None:
    client = MagicMock()
    page = [{"id": "1"}, {"id": "2"}]
    client.get_skills = lambda: _batches(page)

    exporter = SkillsExporter(client)
    results = [batch async for batch in exporter.get_paginated_resources()]

    assert results == [page]
