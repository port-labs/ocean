from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults
from port_ocean.core.integrations.mixins.live_events import LiveEventsMixin
from port_ocean.core.integrations.mixins.utils import selector_hash_from_resource
from port_ocean.core.models import (
    LakehouseDataEntryBatch,
    LakehouseEventType,
    LakehouseOperation,
)
from port_ocean.core.ocean_types import RAW_ITEM
from port_ocean.ocean import Ocean


def _resource(kind: str = "repository", **properties: str) -> ResourceConfig:
    return ResourceConfig(
        kind=kind,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".name",
                    title=".name",
                    blueprint='"service"',
                    properties=properties or {"url": ".links.html.href"},
                    relations={},
                )
            )
        ),
    )


def _raw_results(
    *,
    updated: list[RAW_ITEM] | None = None,
    deleted: list[RAW_ITEM] | None = None,
    trace_id: str | None = "trace-1",
    resource: ResourceConfig | None = None,
    resource_index: int | None = None,
    created_at: datetime | None = None,
) -> WebhookEventRawResults:
    results = WebhookEventRawResults(
        updated_raw_results=updated or [],
        deleted_raw_results=deleted or [],
        webhook_trace_id=trace_id,
        created_at=created_at,
    )
    results.resource = resource or _resource()
    results.resource_index = resource_index
    return results


@pytest.fixture
def posted_batches(mock_ocean: Ocean) -> list[tuple[str, LakehouseDataEntryBatch]]:
    batches: list[tuple[str, LakehouseDataEntryBatch]] = []

    async def post(sync_id: str, batch: LakehouseDataEntryBatch) -> None:
        batches.append((sync_id, batch))

    mock_ocean.port_client.post_integration_raw_data_batch = AsyncMock(side_effect=post)  # type: ignore[method-assign]
    return batches


@pytest.fixture
def mixin(mock_context: PortOceanContext) -> LiveEventsMixin:
    live_events_mixin = LiveEventsMixin()
    live_events_mixin._port_app_config_handler = MagicMock()
    return live_events_mixin


@pytest.mark.asyncio
async def test_sync_raw_results_sends_upserts_raw_without_writing_entities(
    mixin: LiveEventsMixin,
    mock_ocean: Ocean,
    posted_batches: list[tuple[str, LakehouseDataEntryBatch]],
) -> None:
    mock_ocean.port_client.upsert_entity = AsyncMock()  # type: ignore[method-assign]
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    raw = [{"name": "repo-one", "links": {"html": {"href": "https://x"}}}]
    results = _raw_results(updated=raw, created_at=created_at)

    await mixin.sync_raw_results([results])

    [(sync_id, batch)] = posted_batches
    assert sync_id == "trace-1"
    assert batch["event_id"] == "trace-1"
    assert batch["kind"] == "repository"
    assert batch["event_type"] == LakehouseEventType.LIVE_EVENT
    assert batch["type"] == "live-event"
    assert batch["resync_start_time"] == created_at
    [entry] = batch["data"]
    assert entry["items"] == raw
    assert entry["metadata"]["operation"] == LakehouseOperation.UPSERT
    assert entry["metadata"]["resource_index"] == 0
    assert entry["metadata"]["selector_hash"] == selector_hash_from_resource(
        results.resource
    )
    mock_ocean.port_client.upsert_entity.assert_not_called()


@pytest.mark.asyncio
async def test_sync_raw_results_sends_upsert_and_delete_of_one_event_in_one_batch(
    mixin: LiveEventsMixin,
    posted_batches: list[tuple[str, LakehouseDataEntryBatch]],
) -> None:
    await mixin.sync_raw_results(
        [_raw_results(updated=[{"name": "a"}], deleted=[{"name": "b"}])]
    )

    [(_, batch)] = posted_batches
    assert [entry["metadata"]["operation"] for entry in batch["data"]] == [
        LakehouseOperation.UPSERT,
        LakehouseOperation.DELETE,
    ]
    assert batch["data"][1]["items"] == [{"name": "b"}]


@pytest.mark.asyncio
async def test_sync_raw_results_groups_batches_by_event_and_kind(
    mixin: LiveEventsMixin,
    posted_batches: list[tuple[str, LakehouseDataEntryBatch]],
) -> None:
    await mixin.sync_raw_results(
        [
            _raw_results(updated=[{"name": "a"}], trace_id="trace-1"),
            _raw_results(
                updated=[{"name": "b"}],
                trace_id="trace-1",
                resource=_resource("pull-request"),
                resource_index=1,
            ),
            _raw_results(updated=[{"name": "c"}], trace_id="trace-2"),
        ]
    )

    assert sorted((sync_id, batch["kind"]) for sync_id, batch in posted_batches) == [
        ("trace-1", "pull-request"),
        ("trace-1", "repository"),
        ("trace-2", "repository"),
    ]
    pull_request_batch = next(
        batch for _, batch in posted_batches if batch["kind"] == "pull-request"
    )
    assert pull_request_batch["data"][0]["metadata"]["resource_index"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "results",
    [
        pytest.param(_raw_results(), id="empty"),
        pytest.param(
            _raw_results(updated=[{"name": "a"}], trace_id=None), id="no_trace"
        ),
    ],
)
async def test_sync_raw_results_skips_events_without_data_or_trace_id(
    mixin: LiveEventsMixin,
    posted_batches: list[tuple[str, LakehouseDataEntryBatch]],
    results: WebhookEventRawResults,
) -> None:
    await mixin.sync_raw_results([results])

    assert posted_batches == []


@pytest.mark.asyncio
async def test_sync_raw_results_skips_results_without_resource(
    mixin: LiveEventsMixin,
    posted_batches: list[tuple[str, LakehouseDataEntryBatch]],
) -> None:
    results = WebhookEventRawResults(
        updated_raw_results=[{"name": "a"}],
        deleted_raw_results=[],
        webhook_trace_id="trace-1",
    )

    await mixin.sync_raw_results([results])

    assert posted_batches == []


@pytest.mark.asyncio
async def test_sync_raw_results_propagates_lakehouse_failures(
    mixin: LiveEventsMixin,
    mock_ocean: Ocean,
) -> None:
    mock_ocean.port_client.post_integration_raw_data_batch = AsyncMock(  # type: ignore[method-assign]
        side_effect=RuntimeError("lakehouse down")
    )

    with pytest.raises(RuntimeError, match="lakehouse down"):
        await mixin.sync_raw_results([_raw_results(updated=[{"name": "a"}])])
