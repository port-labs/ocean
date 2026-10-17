"""Resources grouped at fetch time: blocks sharing a resourceId fetch once in DSP mode."""

from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from port_ocean.clients.port.types import UserAgentType
from port_ocean.context.event import EventType, event_context
from port_ocean.context.ocean import PortOceanContext
from port_ocean.context.resource import resource_context
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from port_ocean.core.integrations.mixins import SyncRawMixin
from port_ocean.core.integrations.mixins.sync_raw import (
    FetchUnit,
    group_resources_for_fetch,
)
from port_ocean.helpers.metric.metric import MetricResourceKind
from port_ocean.ocean import Ocean

SYNC_RAW = "port_ocean.core.integrations.mixins.sync_raw"


def make_block(
    kind: str,
    blueprint: str = "service",
    resource_id: str | None = None,
    query: str = "true",
    items_to_parse: str | None = None,
) -> ResourceConfig:
    raw: dict[str, Any] = {
        "kind": kind,
        "selector": {"query": query},
        "port": {
            "entity": {
                "mappings": {
                    "identifier": ".id",
                    "blueprint": f'"{blueprint}"',
                    "properties": {},
                }
            }
        },
    }
    if resource_id:
        raw["resourceId"] = resource_id
    if items_to_parse:
        raw["port"]["itemsToParse"] = items_to_parse
    return ResourceConfig.parse_obj(raw)


def _slots(units: list[FetchUnit]) -> list[tuple[str, bool]]:
    return [(unit.kind_identifier, unit.grouped) for unit in units]


class TestGroupResourcesForFetch:
    def test_blocks_sharing_an_id_fetch_once_under_the_head(self) -> None:
        resources = [
            make_block("pr", "pr_title", "res_pr"),
            make_block("issue", "issue", "res_issue"),
            make_block("pr", "pr_author", "res_pr", query=".draft == false"),
        ]

        units = group_resources_for_fetch(resources, dsp_enabled=True)

        assert _slots(units) == [("pr-0", True), ("issue-1", False)]
        assert units[0].resource is resources[0]

    def test_a_group_whose_items_to_parse_differ_is_not_grouped(self) -> None:
        resources = [
            make_block("file", "a", "res_file", items_to_parse=".a"),
            make_block("file", "b", "res_file", items_to_parse=".b"),
        ]

        units = group_resources_for_fetch(resources, dsp_enabled=True)

        assert _slots(units) == [("file-0", False), ("file-1", False)]

    def test_without_ids_every_block_is_its_own_fetch(self) -> None:
        resources = [make_block("pr", "a"), make_block("pr", "b")]

        units = group_resources_for_fetch(resources, dsp_enabled=True)

        assert _slots(units) == [("pr-0", False), ("pr-1", False)]

    def test_ids_are_ignored_outside_dsp_mode(self) -> None:
        resources = [
            make_block("pr", "a", "res_pr"),
            make_block("pr", "b", "res_pr"),
        ]

        units = group_resources_for_fetch(resources, dsp_enabled=False)

        assert _slots(units) == [("pr-0", False), ("pr-1", False)]


class TestPortAppConfigResourceId:
    def test_resource_id_is_parsed_and_kept_out_of_the_request_to_port(
        self,
    ) -> None:
        config = PortAppConfig(resources=[make_block("pr", resource_id="res_pr")])

        assert config.resources[0].resource_id == "res_pr"
        assert "resourceId" not in config.to_request()["resources"][0]

    def test_the_dsp_lifecycle_mapping_carries_the_ids_port_served(self) -> None:
        config = PortAppConfig(
            resources=[make_block("pr", resource_id="res_pr"), make_block("issue")]
        )

        resources = config.to_dsp_lifecycle_mapping()["resources"]

        assert resources[0]["resourceId"] == "res_pr"
        assert "resourceId" not in resources[1]


@pytest.fixture
def mixin(mock_context: PortOceanContext) -> SyncRawMixin:
    sync_raw_mixin = SyncRawMixin()
    sync_raw_mixin._entity_processor = MagicMock()
    sync_raw_mixin._entities_state_applier = MagicMock()
    sync_raw_mixin._port_app_config_handler = MagicMock()
    return sync_raw_mixin


@pytest.fixture
def lifecycle_client(mock_ocean: Ocean) -> MagicMock:
    client = MagicMock()
    client.notify_resync_started = AsyncMock()
    client.notify_resync_finished = AsyncMock()
    client.notify_resync_failed = AsyncMock()
    client.notify_resync_aborted = AsyncMock()
    mock_ocean.lifecycle_client = client
    mock_ocean.config.integration.identifier = "integration-id"
    mock_ocean.config.integration.type = "integration-type"
    mock_ocean.metrics.report_sync_metrics = AsyncMock(return_value=None)  # type: ignore[method-assign]
    mock_ocean.metrics.report_kind_sync_metrics = AsyncMock(return_value=None)  # type: ignore[method-assign]
    mock_ocean.metrics.send_metrics_to_webhook = AsyncMock(return_value=None)  # type: ignore[method-assign]
    return client


def _serve_config(mixin: SyncRawMixin, config: PortAppConfig) -> None:
    handler = MagicMock()
    handler.get_port_app_config = AsyncMock(return_value=config)
    mixin._port_app_config_handler = handler


async def test_dsp_resync_fetches_a_grouped_resource_once_under_its_head_slot(
    mixin: SyncRawMixin, mock_ocean: Ocean, lifecycle_client: MagicMock
) -> None:
    resources = [
        make_block("pr", "pr_title", "res_pr"),
        make_block("issue", "issue"),
        make_block("pr", "pr_author", "res_pr", query=".draft == false"),
    ]
    config = PortAppConfig(resources=resources)
    _serve_config(mixin, config)
    mixin.process_resource = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

    with patch(f"{SYNC_RAW}.is_dsp_mode_enabled", AsyncMock(return_value=True)):
        await mixin.sync_raw_all(user_agent_type=UserAgentType.exporter)

    calls = mixin.process_resource.await_args_list
    assert [(call.args[0], call.args[1], call.kwargs) for call in calls] == [
        (resources[0], 0, {"grouped": True}),
        (resources[1], 1, {}),
    ]
    reported = mock_ocean.metrics.report_sync_metrics.await_args_list[0].kwargs  # type: ignore[attr-defined]
    assert reported["kinds"] == ["pr-0", "issue-1"]
    assert reported["blueprints"] == ['"pr_title"', '"issue"']
    started = lifecycle_client.notify_resync_started.await_args.kwargs
    assert started["mapping"] == config.to_dsp_lifecycle_mapping()
    assert [r.get("resourceId") for r in started["mapping"]["resources"]] == [
        "res_pr",
        None,
        "res_pr",
    ]


async def test_dsp_resync_without_ids_processes_every_block(
    mixin: SyncRawMixin, mock_ocean: Ocean, lifecycle_client: MagicMock
) -> None:
    resources = [make_block("pr", "a"), make_block("pr", "b")]
    _serve_config(mixin, PortAppConfig(resources=resources))
    mixin.process_resource = AsyncMock(return_value=([], []))  # type: ignore[method-assign]

    with patch(f"{SYNC_RAW}.is_dsp_mode_enabled", AsyncMock(return_value=True)):
        await mixin.sync_raw_all(user_agent_type=UserAgentType.exporter)

    calls = mixin.process_resource.await_args_list
    # No ids: process_resource is called exactly as before grouping existed.
    assert [(call.args[1], call.kwargs) for call in calls] == [(0, {}), (1, {})]
    reported = mock_ocean.metrics.report_sync_metrics.await_args_list[0].kwargs  # type: ignore[attr-defined]
    assert reported["kinds"] == ["pr-0", "pr-1"]


async def test_abortion_reports_the_pending_units(
    mixin: SyncRawMixin, mock_ocean: Ocean, lifecycle_client: MagicMock
) -> None:
    units = [
        FetchUnit(0, make_block("pr", "pr_title", "res_pr"), grouped=True),
        FetchUnit(1, make_block("issue", "issue")),
        FetchUnit(3, make_block("team", "team")),
    ]

    await mixin._handle_resync_abortion([([], [])], units, dsp_enabled=True)

    reported = [
        call.kwargs["kind"]
        for call in mock_ocean.metrics.report_kind_sync_metrics.await_args_list  # type: ignore[attr-defined]
    ]
    assert reported == ["issue-1", "team-3"]
    assert MetricResourceKind.RECONCILIATION not in reported


@pytest.fixture
def lakehouse_buffer() -> Generator[MagicMock, None, None]:
    buffer = MagicMock()
    buffer.add = AsyncMock()
    buffer.flush = AsyncMock()
    with (
        patch(f"{SYNC_RAW}.LakehouseBuffer", MagicMock(return_value=buffer)),
        patch(f"{SYNC_RAW}.is_lakehouse_data_enabled", AsyncMock(return_value=True)),
        patch(f"{SYNC_RAW}.is_dsp_mode_enabled", AsyncMock(return_value=True)),
    ):
        yield buffer


async def _register_pages(
    mixin: SyncRawMixin, resource: ResourceConfig, grouped: bool
) -> None:
    async def pages() -> AsyncGenerator[list[dict[str, Any]], None]:
        yield [{"id": "2"}]

    mixin._get_resource_raw_results = AsyncMock(  # type: ignore[method-assign]
        return_value=([{"id": "1"}, pages()], [])
    )
    async with event_context(EventType.RESYNC, trigger_type="machine") as event:
        event.port_app_config = PortAppConfig(resources=[resource])
        async with resource_context(resource, 0):
            await mixin._register_in_batches(
                resource, UserAgentType.exporter, 0, dsp_enabled=True, grouped=grouped
            )


async def test_grouped_fetch_stamps_the_resource_id_on_lakehouse_entries(
    mixin: SyncRawMixin, mock_ocean: Ocean, lakehouse_buffer: MagicMock
) -> None:
    await _register_pages(mixin, make_block("pr", resource_id="res_pr"), True)

    entries = [call.args[0] for call in lakehouse_buffer.add.await_args_list]
    assert len(entries) == 2
    assert [entry["metadata"]["resource_id"] for entry in entries] == [
        "res_pr",
        "res_pr",
    ]
    assert [entry["metadata"]["resource_index"] for entry in entries] == [0, 0]


async def test_ungrouped_fetch_does_not_stamp_the_resource_id(
    mixin: SyncRawMixin, mock_ocean: Ocean, lakehouse_buffer: MagicMock
) -> None:
    await _register_pages(mixin, make_block("pr", resource_id="res_pr"), False)

    entries = [call.args[0] for call in lakehouse_buffer.add.await_args_list]
    assert len(entries) == 2
    assert all("resource_id" not in entry["metadata"] for entry in entries)
