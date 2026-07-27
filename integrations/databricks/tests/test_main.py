from typing import Any, AsyncGenerator, AsyncIterator, Generator, cast
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from port_ocean.context.event import EventContext, _event_context_stack
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

TEST_CONFIG: dict[str, str] = {
    "workspace_url": "https://workspace.cloud.databricks.com",
    "token": "test-token",
}


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    from integration import DatabricksIntegration
    from port_ocean.context.ocean import ocean as ocean_proxy

    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = dict(TEST_CONFIG)
        mock_ocean_app.config.client_timeout = 30.0
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.base_url = None
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        mock_ocean_app.integration = DatabricksIntegration(mock_ocean_app)

        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass

    # Regardless of which fixture (in this file or another test module) performed
    # the process-wide `initialize_port_ocean_context` call, make sure `.integration`
    # is a real DatabricksIntegration instance. The `@ocean.on_resync`/`@ocean.on_start`
    # decorators in main.py delegate to `ocean.integration.on_resync`/`on_start`, which
    # must return the original function unchanged rather than a generic MagicMock.
    if not isinstance(ocean_proxy.app.integration, DatabricksIntegration):
        ocean_proxy.app.integration = DatabricksIntegration(ocean_proxy.app)  # type: ignore[arg-type]


@pytest.fixture
def mock_event_context() -> Generator[MagicMock, None, None]:
    mock_event = MagicMock(spec=EventContext)
    mock_event.resource_config = MagicMock()
    mock_event.attributes = {}

    _event_context_stack.push(mock_event)
    try:
        yield mock_event
    finally:
        _event_context_stack.pop()


async def _one_batch(
    batch: list[dict[str, Any]],
) -> AsyncGenerator[list[dict[str, Any]], None]:
    yield batch


def _resync_batches(resync_fn: Any, kind: str) -> AsyncIterator[list[dict[str, Any]]]:
    """Calls a (possibly Optional, per the `@ocean.on_resync` typing) resync
    function and casts the result to a plain async iterator for the test to
    consume, mirroring the `assert ... is not None` + `cast(...)` idiom used
    elsewhere in the codebase for testing `@ocean.on_resync`-decorated functions.
    """
    assert resync_fn is not None
    return cast(AsyncIterator[list[dict[str, Any]]], resync_fn(kind))


@pytest.mark.asyncio
async def test_clusters_resync_yields_client_batches(
    mock_event_context: MagicMock,
) -> None:
    import main

    mock_client = MagicMock()
    mock_client.get_clusters.return_value = _one_batch([{"cluster_id": "c1"}])

    with patch("main.DatabricksClient") as mock_class:
        mock_class.from_ocean_configuration.return_value = mock_client
        batches = [
            batch
            async for batch in _resync_batches(main.on_clusters_resync, "clusters")
        ]

    assert batches == [[{"cluster_id": "c1"}]]


@pytest.mark.asyncio
async def test_jobs_resync_passes_expand_tasks_selector(
    mock_event_context: MagicMock,
) -> None:
    import main

    mock_event_context.resource_config.selector.expand_tasks = True
    mock_client = MagicMock()
    mock_client.get_jobs.return_value = _one_batch([{"job_id": 1}])

    with patch("main.DatabricksClient") as mock_class:
        mock_class.from_ocean_configuration.return_value = mock_client
        batches = [
            batch async for batch in _resync_batches(main.on_jobs_resync, "jobs")
        ]

    assert batches == [[{"job_id": 1}]]
    mock_client.get_jobs.assert_called_once_with(expand_tasks=True)


@pytest.mark.asyncio
async def test_job_runs_resync_passes_completed_only_selector(
    mock_event_context: MagicMock,
) -> None:
    import main

    mock_event_context.resource_config.selector.completed_only = True
    mock_client = MagicMock()
    mock_client.get_job_runs.return_value = _one_batch([{"run_id": 1}])

    with patch("main.DatabricksClient") as mock_class:
        mock_class.from_ocean_configuration.return_value = mock_client
        batches = [
            batch
            async for batch in _resync_batches(main.on_job_runs_resync, "job_runs")
        ]

    assert batches == [[{"run_id": 1}]]
    mock_client.get_job_runs.assert_called_once_with(completed_only=True)


@pytest.mark.asyncio
async def test_pipelines_resync_yields_client_batches(
    mock_event_context: MagicMock,
) -> None:
    import main

    mock_client = MagicMock()
    mock_client.get_pipelines.return_value = _one_batch([{"pipeline_id": "p1"}])

    with patch("main.DatabricksClient") as mock_class:
        mock_class.from_ocean_configuration.return_value = mock_client
        batches = [
            batch
            async for batch in _resync_batches(main.on_pipelines_resync, "pipelines")
        ]

    assert batches == [[{"pipeline_id": "p1"}]]


@pytest.mark.asyncio
async def test_sql_warehouses_resync_yields_client_batches(
    mock_event_context: MagicMock,
) -> None:
    import main

    mock_client = MagicMock()
    mock_client.get_sql_warehouses.return_value = _one_batch([{"id": "w1"}])

    with patch("main.DatabricksClient") as mock_class:
        mock_class.from_ocean_configuration.return_value = mock_client
        batches = [
            batch
            async for batch in _resync_batches(
                main.on_sql_warehouses_resync, "sql_warehouses"
            )
        ]

    assert batches == [[{"id": "w1"}]]


@pytest.mark.asyncio
async def test_catalogs_resync_passes_catalog_names_selector(
    mock_event_context: MagicMock,
) -> None:
    import main

    mock_event_context.resource_config.selector.catalog_names = ["main"]
    mock_client = MagicMock()
    mock_client.get_all_catalogs.return_value = _one_batch([{"name": "main"}])

    with patch("main.DatabricksClient") as mock_class:
        mock_class.from_ocean_configuration.return_value = mock_client
        batches = [
            batch
            async for batch in _resync_batches(main.on_catalogs_resync, "catalogs")
        ]

    assert batches == [[{"name": "main"}]]
    mock_client.get_all_catalogs.assert_called_once_with(catalog_names=["main"])


@pytest.mark.asyncio
async def test_schemas_resync_uses_fan_out_helper(
    mock_event_context: MagicMock,
) -> None:
    import main

    mock_event_context.resource_config.selector.catalog_names = None
    mock_client = MagicMock()
    mock_client.get_all_schemas.return_value = _one_batch(
        [{"name": "default", "catalog_name": "main"}]
    )

    with patch("main.DatabricksClient") as mock_class:
        mock_class.from_ocean_configuration.return_value = mock_client
        batches = [
            batch async for batch in _resync_batches(main.on_schemas_resync, "schemas")
        ]

    assert batches == [[{"name": "default", "catalog_name": "main"}]]
    mock_client.get_all_schemas.assert_called_once_with(catalog_names=None)


@pytest.mark.asyncio
async def test_tables_resync_uses_fan_out_helper(
    mock_event_context: MagicMock,
) -> None:
    import main

    mock_event_context.resource_config.selector.catalog_names = None
    mock_client = MagicMock()
    mock_client.get_all_tables.return_value = _one_batch(
        [{"name": "orders", "catalog_name": "main", "schema_name": "default"}]
    )

    with patch("main.DatabricksClient") as mock_class:
        mock_class.from_ocean_configuration.return_value = mock_client
        batches = [
            batch async for batch in _resync_batches(main.on_tables_resync, "tables")
        ]

    assert batches == [
        [{"name": "orders", "catalog_name": "main", "schema_name": "default"}]
    ]
    mock_client.get_all_tables.assert_called_once_with(catalog_names=None)


@pytest.mark.asyncio
async def test_on_start_skips_webhook_when_event_listener_is_once() -> None:
    import main

    mock_client = MagicMock()
    with (
        patch("main.DatabricksClient") as mock_class,
        patch("main.ocean") as mock_ocean,
    ):
        mock_class.from_ocean_configuration.return_value = mock_client
        mock_ocean.event_listener_type = "ONCE"

        await main.on_start()

    mock_client.create_webhook_destination_if_not_exists.assert_not_called()


@pytest.mark.asyncio
async def test_on_start_registers_webhook_when_base_url_present() -> None:
    import main

    mock_client = MagicMock()
    mock_client.create_webhook_destination_if_not_exists = AsyncMock()

    with (
        patch("main.DatabricksClient") as mock_class,
        patch("main.ocean") as mock_ocean,
    ):
        mock_class.from_ocean_configuration.return_value = mock_client
        mock_ocean.event_listener_type = "POLLING"
        mock_ocean.app.base_url = "https://app.example.com"

        await main.on_start()

    mock_client.create_webhook_destination_if_not_exists.assert_called_once_with(
        "https://app.example.com/integration/webhook"
    )


@pytest.mark.asyncio
async def test_on_start_skips_webhook_when_no_base_url() -> None:
    import main

    mock_client = MagicMock()
    mock_client.create_webhook_destination_if_not_exists = AsyncMock()

    with (
        patch("main.DatabricksClient") as mock_class,
        patch("main.ocean") as mock_ocean,
    ):
        mock_class.from_ocean_configuration.return_value = mock_client
        mock_ocean.event_listener_type = "POLLING"
        mock_ocean.app.base_url = None

        await main.on_start()

    mock_client.create_webhook_destination_if_not_exists.assert_not_called()


@pytest.mark.asyncio
async def test_on_start_continues_when_webhook_registration_fails() -> None:
    import main

    mock_client = MagicMock()
    mock_client.create_webhook_destination_if_not_exists = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "boom", request=MagicMock(), response=MagicMock(status_code=500)
        )
    )

    with (
        patch("main.DatabricksClient") as mock_class,
        patch("main.ocean") as mock_ocean,
    ):
        mock_class.from_ocean_configuration.return_value = mock_client
        mock_ocean.event_listener_type = "POLLING"
        mock_ocean.app.base_url = "https://app.example.com"

        await main.on_start()

    mock_client.create_webhook_destination_if_not_exists.assert_called_once()


@pytest.mark.asyncio
async def test_on_start_handles_missing_credentials_gracefully() -> None:
    import main
    from clients.auth import MissingIntegrationCredentialException

    with patch("main.DatabricksClient") as mock_class:
        mock_class.from_ocean_configuration.side_effect = (
            MissingIntegrationCredentialException("missing creds")
        )
        await main.on_start()
