import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Awaitable, Callable, Generator, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from loguru import logger

from port_ocean.clients.dsp.lifecycle import GranularityType
from port_ocean.clients.port.types import UserAgentType
from port_ocean.context.event import EventType, event_context
from port_ocean.context.ocean import PortOceanContext
from port_ocean.context.resource import resource_context
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortAppConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.mixins import SyncRawMixin
from port_ocean.core.models import (
    LakehouseDataEntryBatch,
    LakehouseEventType,
    LakehouseOperation,
)
from port_ocean.core.ocean_types import ETLPhase, RAW_RESULT
from port_ocean.exceptions.core import KindNotImplementedException
from port_ocean.helpers.metric.metric import SyncState
from port_ocean.ocean import Ocean


@pytest.fixture(autouse=True)
def mock_resource_monitoring() -> Generator[None, None, None]:
    with (
        patch(
            "port_ocean.core.integrations.mixins.sync_raw.start_monitoring",
            AsyncMock(return_value=None),
        ),
        patch(
            "port_ocean.core.integrations.mixins.sync_raw.stop_monitoring",
            AsyncMock(return_value=None),
        ),
        patch(
            "port_ocean.core.integrations.mixins.sync_raw.start_kind_tracking",
            MagicMock(return_value=None),
        ),
        patch(
            "port_ocean.core.integrations.mixins.sync_raw.stop_kind_tracking",
            MagicMock(return_value=None),
        ),
    ):
        yield


@pytest.fixture
def lifecycle_client(mock_ocean: Ocean) -> MagicMock:
    client = MagicMock()
    for method in (
        "notify_resync_started",
        "notify_resync_finished",
        "notify_resync_failed",
        "notify_resync_aborted",
        "notify_started",
        "notify_finished",
        "notify_failed",
        "notify_aborted",
    ):
        setattr(client, method, AsyncMock())
    client.get_resync_status = AsyncMock(return_value="running")
    mock_ocean.lifecycle_client = client
    mock_ocean.config.integration.identifier = "integration-id"
    mock_ocean.config.integration.type = "integration-type"
    return client


@pytest.fixture
def posted_batches(mock_ocean: Ocean) -> list[tuple[str, LakehouseDataEntryBatch]]:
    batches: list[tuple[str, LakehouseDataEntryBatch]] = []

    async def post(sync_id: str, batch: LakehouseDataEntryBatch) -> None:
        batches.append((sync_id, batch))

    mock_ocean.port_client.post_integration_raw_data_batch = AsyncMock(side_effect=post)  # type: ignore[method-assign]
    return batches


@pytest.fixture
def mock_sync_raw_mixin(
    mock_context: PortOceanContext,
    mock_ocean: Ocean,
    mock_port_app_config_handler: MagicMock,
    lifecycle_client: MagicMock,
    posted_batches: list[tuple[str, LakehouseDataEntryBatch]],
) -> SyncRawMixin:
    mock_ocean.config.send_raw_data_examples = False
    mock_ocean.config.lakehouse_buffer_interval_seconds = 3600
    mock_ocean.config.lakehouse_buffer_max_count = 1000
    mock_ocean.metrics.send_metrics_to_webhook = AsyncMock(return_value=None)  # type: ignore[method-assign]

    sync_raw_mixin = SyncRawMixin()
    sync_raw_mixin._port_app_config_handler = mock_port_app_config_handler

    raw_data = [
        {"id": "entity_1", "name": "Entity 1", "web_url": "https://example.com/1"},
        {"id": "entity_2", "name": "Entity 2", "web_url": "https://example.com/2"},
    ]

    async def raw_results_generator() -> AsyncGenerator[list[dict[str, Any]], None]:
        yield raw_data

    sync_raw_mixin._get_resource_raw_results = AsyncMock(  # type: ignore[method-assign]
        return_value=([raw_results_generator()], [])
    )
    return sync_raw_mixin


def _capture_loguru_extras() -> tuple[list[dict[str, Any]], int]:
    """Add a loguru sink that captures record extras. Returns (records_list, sink_id)."""
    records: list[dict[str, Any]] = []
    sink_id = logger.add(lambda msg: records.append(dict(msg.record["extra"])))
    return records, sink_id


def _resource_config_for_kind(kind: str) -> ResourceConfig:
    return ResourceConfig(
        kind=kind,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".name",
                    blueprint='"service"',
                    properties={"url": ".web_url"},
                    relations={},
                )
            )
        ),
    )


async def _resync_handler(kind: str) -> list[dict[str, str]]:
    return [{"id": "1"}]


@pytest.mark.asyncio
async def test_sync_raw_all_hands_raw_items_to_lakehouse_without_transforming(
    mock_sync_raw_mixin: SyncRawMixin,
    posted_batches: list[tuple[str, LakehouseDataEntryBatch]],
    lifecycle_client: MagicMock,
    mock_ocean: Ocean,
) -> None:
    mock_ocean.port_client.upsert_entities_in_batches = AsyncMock()  # type: ignore[method-assign]

    result = await mock_sync_raw_mixin.sync_raw_all(
        trigger_type="machine", user_agent_type=UserAgentType.exporter
    )

    assert result is True
    assert len(posted_batches) == 1
    sync_id, batch = posted_batches[0]
    assert batch["kind"] == "project"
    assert batch["event_type"] == LakehouseEventType.RESYNC
    [entry] = batch["data"]
    assert entry["metadata"]["operation"] == LakehouseOperation.UPSERT
    assert entry["metadata"]["resource_index"] == 0
    assert [item["id"] for item in entry["items"]] == ["entity_1", "entity_2"]
    mock_ocean.port_client.upsert_entities_in_batches.assert_not_called()
    assert (
        lifecycle_client.notify_resync_started.await_args.kwargs["resync_id"] == sync_id
    )
    lifecycle_client.notify_resync_finished.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_raw_sends_live_event_upsert_per_matching_resource(
    mock_sync_raw_mixin: SyncRawMixin,
    mock_port_app_config: PortAppConfig,
    posted_batches: list[tuple[str, LakehouseDataEntryBatch]],
) -> None:
    mock_port_app_config.resources.append(_resource_config_for_kind("project"))
    raw = [{"id": "1", "name": "one"}]

    async with event_context(EventType.HTTP_REQUEST, trigger_type="machine") as event:
        event.port_app_config = mock_port_app_config
        await mock_sync_raw_mixin.register_raw("project", raw, UserAgentType.exporter)

    [(event_id, batch)] = posted_batches
    assert batch["event_id"] == event_id
    assert batch["event_type"] == LakehouseEventType.LIVE_EVENT
    assert batch["kind"] == "project"
    assert [entry["metadata"]["resource_index"] for entry in batch["data"]] == [0, 1]
    assert all(
        entry["metadata"]["operation"] == LakehouseOperation.UPSERT
        for entry in batch["data"]
    )
    assert batch["data"][0]["items"] == raw


@pytest.mark.asyncio
async def test_unregister_raw_sends_live_event_delete(
    mock_sync_raw_mixin: SyncRawMixin,
    mock_port_app_config: PortAppConfig,
    posted_batches: list[tuple[str, LakehouseDataEntryBatch]],
) -> None:
    async with event_context(EventType.HTTP_REQUEST, trigger_type="machine") as event:
        event.port_app_config = mock_port_app_config
        await mock_sync_raw_mixin.unregister_raw(
            "project", [{"id": "1"}], UserAgentType.exporter
        )

    [(_, batch)] = posted_batches
    [entry] = batch["data"]
    assert entry["metadata"]["operation"] == LakehouseOperation.DELETE


@pytest.mark.asyncio
async def test_register_raw_skips_kinds_without_resources(
    mock_sync_raw_mixin: SyncRawMixin,
    mock_port_app_config: PortAppConfig,
    posted_batches: list[tuple[str, LakehouseDataEntryBatch]],
) -> None:
    async with event_context(EventType.HTTP_REQUEST, trigger_type="machine") as event:
        event.port_app_config = mock_port_app_config
        await mock_sync_raw_mixin.register_raw(
            "unmapped-kind", [{"id": "1"}], UserAgentType.exporter
        )

    assert posted_batches == []


@pytest.mark.asyncio
async def test_on_resync_start_hooks_are_called(
    mock_sync_raw_mixin: SyncRawMixin,
) -> None:
    resync_start_called = False

    async def on_resync_start() -> None:
        nonlocal resync_start_called
        resync_start_called = True

    mock_sync_raw_mixin.on_resync_start(on_resync_start)
    mock_sync_raw_mixin._get_resource_raw_results = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

    await mock_sync_raw_mixin.sync_raw_all(
        trigger_type="machine", user_agent_type=UserAgentType.exporter
    )

    assert resync_start_called, "on_resync_start hook was not called"


@pytest.mark.asyncio
async def test_sync_raw_all_clears_blueprint_cache_on_start_and_finish(
    mock_sync_raw_mixin: SyncRawMixin,
    mock_ocean: Ocean,
) -> None:
    invalidate_mock = MagicMock(wraps=mock_ocean.port_client.clear_blueprint_cache)
    mock_ocean.port_client.clear_blueprint_cache = invalidate_mock  # type: ignore[method-assign]
    mock_sync_raw_mixin._get_resource_raw_results = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

    await mock_sync_raw_mixin.sync_raw_all(
        trigger_type="machine", user_agent_type=UserAgentType.exporter
    )

    assert invalidate_mock.call_count == 2


@pytest.mark.asyncio
async def test_sync_raw_all_empty_resources_notifies_lifecycle_and_skips_sync(
    mock_sync_raw_mixin: SyncRawMixin,
    mock_port_app_config_handler: MagicMock,
    lifecycle_client: MagicMock,
) -> None:
    mock_port_app_config_handler.get_port_app_config = AsyncMock(
        return_value=PortAppConfig(resources=[])
    )
    mock_sync_raw_mixin._get_resource_raw_results = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

    result = await mock_sync_raw_mixin.sync_raw_all(
        trigger_type="machine", user_agent_type=UserAgentType.exporter
    )

    assert result is True
    mock_sync_raw_mixin._get_resource_raw_results.assert_not_called()
    lifecycle_client.notify_resync_started.assert_awaited_once()
    started_kwargs = lifecycle_client.notify_resync_started.await_args.kwargs
    assert started_kwargs["integration_id"] == "integration-id"
    assert started_kwargs["integration_type"] == "integration-type"
    assert started_kwargs["sync_type"] == "full_sync"
    assert started_kwargs["mapping"]["resources"] == []
    lifecycle_client.notify_resync_finished.assert_awaited_once()
    lifecycle_client.notify_resync_failed.assert_not_awaited()
    lifecycle_client.notify_resync_aborted.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_resync_complete_hooks_are_called_on_success(
    mock_sync_raw_mixin: SyncRawMixin,
) -> None:
    resync_complete_called = False

    async def on_resync_complete() -> None:
        nonlocal resync_complete_called
        resync_complete_called = True

    mock_sync_raw_mixin.on_resync_complete(on_resync_complete)
    mock_sync_raw_mixin._get_resource_raw_results = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

    await mock_sync_raw_mixin.sync_raw_all(
        trigger_type="machine", user_agent_type=UserAgentType.exporter
    )

    assert resync_complete_called, "on_resync_complete hook was not called"


@pytest.mark.asyncio
async def test_resync_with_kind_errors_returns_false_and_notifies_failed(
    mock_sync_raw_mixin: SyncRawMixin,
    lifecycle_client: MagicMock,
) -> None:
    mock_sync_raw_mixin._get_resource_raw_results.side_effect = Exception("Test error")  # type: ignore[attr-defined]

    result = await mock_sync_raw_mixin.sync_raw_all(
        trigger_type="machine", user_agent_type=UserAgentType.exporter
    )

    assert result is False
    lifecycle_client.notify_failed.assert_awaited_once()
    lifecycle_client.notify_resync_failed.assert_awaited_once()
    lifecycle_client.notify_resync_finished.assert_not_awaited()


@pytest.mark.asyncio
async def test_resync_with_kind_errors_raises_when_not_silent(
    mock_sync_raw_mixin: SyncRawMixin,
) -> None:
    mock_sync_raw_mixin._get_resource_raw_results.side_effect = Exception("Test error")  # type: ignore[attr-defined]

    with pytest.raises(ExceptionGroup):
        await mock_sync_raw_mixin.sync_raw_all(
            trigger_type="machine",
            user_agent_type=UserAgentType.exporter,
            silent=False,
        )


@pytest.mark.asyncio
async def test_multiple_on_resync_start_on_resync_complete_hooks_called_in_order(
    mock_sync_raw_mixin: SyncRawMixin,
) -> None:
    call_order: list[str] = []

    async def on_resync_start1() -> None:
        call_order.append("on_resync_start1")

    async def on_resync_start2() -> None:
        call_order.append("on_resync_start2")

    async def on_resync_complete1() -> None:
        call_order.append("on_resync_complete1")

    async def on_resync_complete2() -> None:
        call_order.append("on_resync_complete2")

    mock_sync_raw_mixin.on_resync_start(on_resync_start1)
    mock_sync_raw_mixin.on_resync_start(on_resync_start2)
    mock_sync_raw_mixin.on_resync_complete(on_resync_complete1)
    mock_sync_raw_mixin.on_resync_complete(on_resync_complete2)
    mock_sync_raw_mixin._get_resource_raw_results = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

    await mock_sync_raw_mixin.sync_raw_all(
        trigger_type="machine", user_agent_type=UserAgentType.exporter
    )

    assert call_order == [
        "on_resync_start1",
        "on_resync_start2",
        "on_resync_complete1",
        "on_resync_complete2",
    ], "Hooks were not called in the correct order"


@pytest.mark.asyncio
async def test_on_resync_start_hook_error_prevents_resync(
    mock_sync_raw_mixin: SyncRawMixin,
) -> None:
    resync_complete_called = False
    resync_proceeded = False

    async def on_resync_start() -> None:
        raise Exception("Before resync error")

    async def on_resync_complete() -> None:
        nonlocal resync_complete_called
        resync_complete_called = True

    mock_sync_raw_mixin.on_resync_start(on_resync_start)
    mock_sync_raw_mixin.on_resync_complete(on_resync_complete)
    original_get_resource_raw_results = mock_sync_raw_mixin._get_resource_raw_results

    async def track_resync(*args: Any, **kwargs: Any) -> Any:
        nonlocal resync_proceeded
        resync_proceeded = True
        return await original_get_resource_raw_results(*args, **kwargs)

    mock_sync_raw_mixin._get_resource_raw_results = track_resync  # type: ignore[method-assign]

    with pytest.raises(Exception, match="Before resync error"):
        await mock_sync_raw_mixin.sync_raw_all(
            trigger_type="machine", user_agent_type=UserAgentType.exporter
        )

    assert not resync_proceeded
    assert not resync_complete_called


@pytest.mark.asyncio
async def test_register_in_batches_sets_extract_etl_phase_in_logger_context(
    mock_sync_raw_mixin: SyncRawMixin,
    mock_resource_config: ResourceConfig,
    mock_port_app_config: PortAppConfig,
) -> None:
    mock_sync_raw_mixin._get_resource_raw_results = AsyncMock(  # type: ignore[method-assign]
        return_value=([{"id": "1", "name": "entity_1"}], [])
    )

    records, sink_id = _capture_loguru_extras()
    try:
        async with event_context(EventType.RESYNC, trigger_type="machine") as event:
            event.port_app_config = mock_port_app_config
            async with resource_context(mock_resource_config, 0):
                await mock_sync_raw_mixin._register_in_batches(
                    mock_resource_config, index=0
                )
    finally:
        logger.remove(sink_id)

    extract_records = [r for r in records if r.get("etl_phase") == ETLPhase.EXTRACT]
    assert len(extract_records) >= 2, "Expected at least 2 logs with etl_phase=extract"


@pytest.mark.asyncio
async def test_complete_resync_sets_reconciliation_etl_phase_in_logger_context(
    mock_sync_raw_mixin: SyncRawMixin,
) -> None:
    records, sink_id = _capture_loguru_extras()
    try:
        async with event_context(EventType.RESYNC, trigger_type="machine"):
            await mock_sync_raw_mixin._complete_resync([], silent=True)
    finally:
        logger.remove(sink_id)

    assert any(r.get("etl_phase") == ETLPhase.RECONCILIATION for r in records)


@pytest.mark.asyncio
async def test_get_resource_raw_results_returns_error_for_unregistered_kind(
    mock_resource_config: ResourceConfig,
) -> None:
    mixin = SyncRawMixin()

    async with event_context(EventType.RESYNC, trigger_type="machine"):
        with patch.object(
            mixin, "_execute_resync_tasks", new_callable=AsyncMock
        ) as mock_execute:
            results, errors = await mixin._get_resource_raw_results(
                mock_resource_config
            )

    mock_execute.assert_not_awaited()
    assert results == []
    assert len(errors) == 1
    assert isinstance(errors[0], KindNotImplementedException)
    assert mock_resource_config.kind in str(errors[0])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "registered_kinds",
    [["service"], [None], ["service", None]],
    ids=["specific", "catch_all", "both"],
)
async def test_get_resource_raw_results_proceeds_when_kind_registered(
    registered_kinds: list[str | None],
) -> None:
    mixin = SyncRawMixin()
    for kind in registered_kinds:
        mixin.on_resync(_resync_handler, kind=kind)

    async with event_context(EventType.RESYNC, trigger_type="machine"):
        with patch.object(
            mixin,
            "_execute_resync_tasks",
            new_callable=AsyncMock,
            return_value=([], []),
        ) as mock_execute:
            results, errors = await mixin._get_resource_raw_results(
                _resource_config_for_kind("service")
            )

    mock_execute.assert_awaited_once()
    assert results == []
    assert errors == []


@pytest.mark.asyncio
async def test_collect_resync_functions_returns_functions_without_setting_logger_context(
    mock_sync_raw_mixin: SyncRawMixin,
    mock_resource_config: ResourceConfig,
) -> None:
    records, sink_id = _capture_loguru_extras()
    try:
        fns = mock_sync_raw_mixin._collect_resync_functions(
            mock_resource_config,
            cast(
                dict[str | None, list[Callable[[str], Awaitable[RAW_RESULT]]]],
                mock_sync_raw_mixin.event_strategy.resync,
            ),
        )
    finally:
        logger.remove(sink_id)

    assert isinstance(fns, list)
    assert all("kind" not in r for r in records)


@pytest.mark.asyncio
async def test_execute_resync_tasks_passes_examples_amount_to_each_async_generator(
    mock_sync_raw_mixin: SyncRawMixin,
    mock_resource_config: ResourceConfig,
) -> None:
    async def generator_one(kind: str) -> AsyncGenerator[list[dict[str, Any]], None]:
        if False:
            yield [{"kind": kind}]

    async def generator_two(kind: str) -> AsyncGenerator[list[dict[str, Any]], None]:
        if False:
            yield [{"kind": kind}]

    with patch(
        "port_ocean.core.integrations.mixins.sync_raw.resync_generator_wrapper",
        side_effect=[generator_one("test-kind"), generator_two("test-kind")],
    ) as mock_wrapper:
        await mock_sync_raw_mixin._execute_resync_tasks(
            [
                cast(Callable[[str], Awaitable[list[dict[Any, Any]]]], generator_one),
                cast(Callable[[str], Awaitable[list[dict[Any, Any]]]], generator_two),
            ],
            mock_resource_config,
            send_raw_data_examples_amount=5,
        )

    assert mock_wrapper.call_count == 2
    assert mock_wrapper.call_args_list[0].kwargs == {"send_raw_data_examples_amount": 5}
    assert mock_wrapper.call_args_list[1].kwargs == {"send_raw_data_examples_amount": 5}


@pytest.mark.asyncio
async def test_process_resource_unexpected_exception_returns_error_in_results(
    mock_sync_raw_mixin: SyncRawMixin,
    mock_resource_config: ResourceConfig,
    mock_ocean: Ocean,
    lifecycle_client: MagicMock,
) -> None:
    mock_sync_raw_mixin._register_in_batches = AsyncMock(
        side_effect=RuntimeError("crash")
    )
    mock_ocean.metrics.event_id = "resync-1"

    async with event_context(
        EventType.RESYNC,
        trigger_type="machine",
        attributes={"resync_start_time": datetime.now(timezone.utc)},
    ):
        extracted, errors = await mock_sync_raw_mixin._process_resource(
            mock_resource_config, index=0
        )

    assert extracted == 0
    assert len(errors) == 1
    assert str(errors[0]) == "crash"
    assert mock_ocean.metrics.sync_state == SyncState.FAILED
    lifecycle_client.notify_failed.assert_awaited_once_with(
        event_id="resync-1",
        granularity=GranularityType.KIND,
        kind_identifier="service-0",
    )
    lifecycle_client.notify_finished.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", [EventType.RESYNC, EventType.INCREMENTAL_RESYNC])
async def test_process_resource_notifies_lifecycle_kind_boundaries(
    mock_sync_raw_mixin: SyncRawMixin,
    mock_resource_config: ResourceConfig,
    mock_ocean: Ocean,
    lifecycle_client: MagicMock,
    event_type: str,
) -> None:
    mock_sync_raw_mixin._register_in_batches = AsyncMock(return_value=(0, []))
    mock_ocean.metrics.event_id = "resync-1"

    async with event_context(event_type, trigger_type="machine"):
        extracted, errors = await mock_sync_raw_mixin._process_resource(
            mock_resource_config, index=0
        )

    assert (extracted, errors) == (0, [])
    lifecycle_client.notify_started.assert_awaited_once_with(
        event_id="resync-1",
        integration_id="integration-id",
        integration_type="integration-type",
        granularity=GranularityType.KIND,
        kind_identifier="service-0",
    )
    lifecycle_client.notify_finished.assert_awaited_once_with(
        event_id="resync-1",
        integration_type="integration-type",
        granularity=GranularityType.KIND,
        kind_identifier="service-0",
    )
    lifecycle_client.notify_failed.assert_not_awaited()
    lifecycle_client.notify_aborted.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_resource_notifies_kind_aborted_on_cancel(
    mock_sync_raw_mixin: SyncRawMixin,
    mock_resource_config: ResourceConfig,
    mock_ocean: Ocean,
    lifecycle_client: MagicMock,
) -> None:
    mock_sync_raw_mixin._register_in_batches = AsyncMock(
        side_effect=asyncio.CancelledError
    )
    mock_ocean.metrics.event_id = "incremental-resync-1"

    with pytest.raises(asyncio.CancelledError):
        async with event_context(EventType.INCREMENTAL_RESYNC, trigger_type="machine"):
            await mock_sync_raw_mixin._process_resource(mock_resource_config, index=0)

    lifecycle_client.notify_started.assert_awaited_once()
    lifecycle_client.notify_aborted.assert_awaited_once_with(
        event_id="incremental-resync-1",
        granularity=GranularityType.KIND,
        kind_identifier="service-0",
    )
    lifecycle_client.notify_finished.assert_not_awaited()
    lifecycle_client.notify_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_raw_all_notifies_resync_started_with_mapping(
    mock_sync_raw_mixin: SyncRawMixin,
    mock_port_app_config: PortAppConfig,
    mock_ocean: Ocean,
    lifecycle_client: MagicMock,
) -> None:
    mock_sync_raw_mixin.process_resource = AsyncMock(return_value=(0, []))  # type: ignore[method-assign]
    expected_mapping = mock_port_app_config.to_dsp_lifecycle_mapping()

    await mock_sync_raw_mixin.sync_raw_all(
        trigger_type="machine", user_agent_type=UserAgentType.exporter
    )

    lifecycle_client.notify_resync_started.assert_awaited_once()
    call_kwargs = lifecycle_client.notify_resync_started.await_args.kwargs
    assert call_kwargs["integration_id"] == "integration-id"
    assert call_kwargs["integration_type"] == "integration-type"
    assert call_kwargs["sync_type"] == "full_sync"
    assert call_kwargs["mapping"] == expected_mapping
    mappings = call_kwargs["mapping"]["resources"][0]["port"]["entity"]["mappings"]
    assert isinstance(mappings, list)
    assert len(mappings) == 1
    lifecycle_client.notify_resync_finished.assert_awaited_once()
    assert "sync_type" not in lifecycle_client.notify_resync_finished.await_args.kwargs
    assert mock_ocean.metrics.event_id != ""


@pytest.mark.asyncio
async def test_poll_for_lifecycle_abort_aborts_event(
    mock_sync_raw_mixin: SyncRawMixin,
    lifecycle_client: MagicMock,
) -> None:
    lifecycle_client.get_resync_status = AsyncMock(return_value="aborted")

    with patch(
        "port_ocean.core.integrations.mixins.sync_raw.asyncio.sleep", AsyncMock()
    ):
        async with event_context(
            EventType.RESYNC,
            trigger_type="machine",
            attributes={"resync_start_time": datetime.now(timezone.utc)},
        ) as current_event:
            assert not current_event.aborted
            await mock_sync_raw_mixin._poll_for_lifecycle_abort("resync-1")
            assert current_event.aborted


@pytest.mark.asyncio
async def test_sync_raw_all_ignores_poll_task_failure_and_completes_cleanup(
    mock_sync_raw_mixin: SyncRawMixin,
    mock_ocean: Ocean,
) -> None:
    mock_sync_raw_mixin._poll_for_lifecycle_abort = AsyncMock(  # type: ignore[method-assign]
        side_effect=RuntimeError("poll failed")
    )
    mock_sync_raw_mixin._get_resource_raw_results = AsyncMock(return_value=([], []))  # type: ignore[method-assign]
    clear_cache = AsyncMock()
    clear_blueprint_cache = MagicMock()
    mock_ocean.cache_provider.clear = clear_cache  # type: ignore[method-assign]
    mock_ocean.port_client.clear_blueprint_cache = clear_blueprint_cache  # type: ignore[method-assign]

    result = await mock_sync_raw_mixin.sync_raw_all(
        trigger_type="machine", user_agent_type=UserAgentType.exporter
    )

    assert result is True
    assert clear_cache.await_count == 2
    assert clear_blueprint_cache.call_count == 2
