import asyncio
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import port_ocean.context.ocean as ocean_module
from port_ocean.context.ocean import initialize_port_ocean_context, PortOceanContext
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

import gcp_core.clients as clients


@pytest.fixture(autouse=True)
def mock_ocean_context() -> Generator[None, None, None]:
    mock_app = MagicMock()
    mock_app.config.integration.config = {"search_all_resources_per_minute_quota": 100}
    mock_app.cache_provider = AsyncMock()
    mock_app.cache_provider.get.return_value = None
    initialize_port_ocean_context(mock_app)
    yield
    ocean_module._port_ocean = PortOceanContext(None)


@pytest.fixture(autouse=True)
def mock_shared_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    default_mock = AsyncMock()
    for name in (
        "AssetServiceAsyncClient",
        "ProjectsAsyncClient",
        "FoldersAsyncClient",
        "OrganizationsAsyncClient",
        "PublisherAsyncClient",
        "SubscriberAsyncClient",
        "CloudQuotasAsyncClient",
    ):
        monkeypatch.setitem(clients._instances, name, default_mock)


@pytest.mark.asyncio
async def test_bounded_concurrency_respected() -> None:
    from gcp_core.search.iterators import iterate_per_available_project

    max_concurrent = 2
    active_count = 0
    max_active = 0
    lock = asyncio.Lock()

    async def mock_callable(
        project: dict[str, Any], **kwargs: Any
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        nonlocal active_count, max_active
        async with lock:
            active_count += 1
            max_active = max(max_active, active_count)
        await asyncio.sleep(0.05)
        yield [{"project": project["name"]}]
        async with lock:
            active_count -= 1

    projects = [{"name": f"project_{i}"} for i in range(6)]

    async def mock_search_all_projects() -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield projects

    with patch(
        "gcp_core.search.iterators.search_all_projects",
        new=mock_search_all_projects,
    ):
        results: list[Any] = []
        async for batch in iterate_per_available_project(
            mock_callable,
            max_concurrent_projects=max_concurrent,
        ):
            results.extend(batch)

    assert max_active <= max_concurrent
    assert len(results) == 6


@pytest.mark.asyncio
async def test_default_concurrency_processes_all_projects() -> None:
    from gcp_core.search.iterators import iterate_per_available_project

    async def mock_callable(
        project: dict[str, Any], **kwargs: Any
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield [project]

    projects = [{"name": f"project_{i}"} for i in range(3)]

    async def mock_search_all_projects() -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield projects

    with patch(
        "gcp_core.search.iterators.search_all_projects",
        new=mock_search_all_projects,
    ):
        results: list[Any] = []
        async for batch in iterate_per_available_project(mock_callable):
            results.extend(batch)

    assert len(results) == 3


@pytest.mark.asyncio
async def test_empty_projects_returns_nothing() -> None:
    from gcp_core.search.iterators import iterate_per_available_project

    async def mock_callable(
        project: dict[str, Any], **kwargs: Any
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield [project]

    async def mock_search_all_projects() -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield []

    with patch(
        "gcp_core.search.iterators.search_all_projects",
        new=mock_search_all_projects,
    ):
        results: list[Any] = []
        async for batch in iterate_per_available_project(mock_callable):
            results.extend(batch)

    assert len(results) == 0


@pytest.mark.asyncio
async def test_kwargs_passed_through_to_callable() -> None:
    from gcp_core.search.iterators import iterate_per_available_project

    received_kwargs: dict[str, Any] = {}

    async def mock_callable(
        project: dict[str, Any], **kwargs: Any
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        received_kwargs.update(kwargs)
        yield [project]

    projects = [{"name": "p1"}]

    async def mock_search_all_projects() -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield projects

    with patch(
        "gcp_core.search.iterators.search_all_projects",
        new=mock_search_all_projects,
    ):
        async for _ in iterate_per_available_project(
            mock_callable,
            asset_type="compute.googleapis.com/Instance",
            max_concurrent_projects=5,
        ):
            pass

    assert received_kwargs["asset_type"] == "compute.googleapis.com/Instance"
    assert "max_concurrent_projects" not in received_kwargs
