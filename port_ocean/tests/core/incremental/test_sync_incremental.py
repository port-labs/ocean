"""Unit tests for SyncRawMixin.sync_incremental."""

from datetime import datetime, timezone
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from port_ocean.clients.dsp.lifecycle import (
    GranularityType,
    SYNC_TYPE_INCREMENTAL_RESYNC,
)
from port_ocean.context.event import EventType
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortAppConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.mixins import SyncRawMixin
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.context.event import event_context
from port_ocean.helpers.metric.metric import SyncState


def make_resource_config(kind: str) -> ResourceConfig:
    return ResourceConfig(
        kind=kind,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".name",
                    blueprint='"service"',
                    properties={},
                    relations={},
                )
            )
        ),
    )


def make_port_app_config(kinds: list[str]) -> PortAppConfig:
    return PortAppConfig(
        enable_merge_entity=False,
        delete_dependent_entities=False,
        create_missing_related_entities=False,
        resources=[make_resource_config(k) for k in kinds],
    )


@pytest.fixture
def mock_port_client() -> MagicMock:
    client = MagicMock()
    client.get_integration_cursor = AsyncMock(return_value=None)
    client.upsert_integration_cursor = AsyncMock()
    client.delete_integration_cursors = AsyncMock()
    return client


@pytest.fixture
def mock_mixin(mock_port_client: MagicMock) -> SyncRawMixin:
    mixin = SyncRawMixin()
    mixin._entity_processor = MagicMock()
    mixin._entities_state_applier = MagicMock()
    port_app_config_handler = MagicMock()
    port_app_config_handler.get_port_app_config = AsyncMock()
    mixin._port_app_config_handler = port_app_config_handler
    mixin.process_resource = AsyncMock(return_value=([], []))  # type: ignore[method-assign]
    return mixin


def configure_app_config(mixin: SyncRawMixin, kinds: list[str]) -> PortAppConfig:
    config = make_port_app_config(kinds)
    cast(MagicMock, mixin._port_app_config_handler).get_port_app_config.return_value = (
        config
    )
    return config


def register_incremental_handler(
    mixin: SyncRawMixin, kind: str | None = None
) -> AsyncMock:
    handler: AsyncMock = AsyncMock()

    async def gen(k: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
        yield [{"id": "1"}]

    handler.side_effect = gen
    mixin.event_strategy["incremental"][kind].append(handler)
    return handler


class TestSyncIncrementalNoHandlers:
    async def test_exits_early_when_no_incremental_kinds_registered(
        self, mock_mixin: SyncRawMixin, mock_port_client: MagicMock
    ) -> None:
        configure_app_config(mock_mixin, ["issue"])

        with patch("port_ocean.core.integrations.mixins.sync_raw.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await mock_mixin.sync_incremental(interval_seconds=900)

        mock_mixin.process_resource.assert_not_called()  # type: ignore[attr-defined]

    async def test_exits_early_when_no_resources_configured(
        self, mock_mixin: SyncRawMixin, mock_port_client: MagicMock
    ) -> None:
        configure_app_config(mock_mixin, [])

        with patch("port_ocean.core.integrations.mixins.sync_raw.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            await mock_mixin.sync_incremental(interval_seconds=900)

        mock_mixin.process_resource.assert_not_called()  # type: ignore[attr-defined]


class TestSyncIncrementalCursorSeeding:
    async def test_seeds_cursor_from_interval_when_no_cursor_stored(
        self, mock_mixin: SyncRawMixin, mock_port_client: MagicMock
    ) -> None:
        """When no cursor exists the effective cursor is seeded, but the cursor
        persisted after success is the ``next_cursor`` snapshot (≈ now)."""
        configure_app_config(mock_mixin, ["issue"])
        register_incremental_handler(mock_mixin, kind="issue")
        mock_port_client.get_integration_cursor.return_value = None

        before = datetime.now(timezone.utc)
        with patch("port_ocean.core.integrations.mixins.sync_raw.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            mock_ocean.config.integration.identifier = "test-integration"
            mock_ocean.config.integration.type = "fake-integration"
            await mock_mixin.sync_incremental(interval_seconds=900)
        after = datetime.now(timezone.utc)

        mock_port_client.upsert_integration_cursor.assert_called_once()
        # The persisted cursor is run_started_at (snapshotted before the fetch).
        saved_cursor: datetime = mock_port_client.upsert_integration_cursor.call_args[
            0
        ][2]
        assert before <= saved_cursor <= after

    async def test_uses_stored_cursor_when_available(
        self, mock_mixin: SyncRawMixin, mock_port_client: MagicMock
    ) -> None:
        stored = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        mock_port_client.get_integration_cursor.return_value = stored
        configure_app_config(mock_mixin, ["issue"])
        register_incremental_handler(mock_mixin, kind="issue")

        with patch("port_ocean.core.integrations.mixins.sync_raw.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            mock_ocean.config.integration.identifier = "test-integration"
            mock_ocean.config.integration.type = "fake-integration"
            await mock_mixin.sync_incremental(interval_seconds=900)

        mock_port_client.upsert_integration_cursor.assert_called_once()


class TestSyncIncrementalCursorScope:
    async def test_handler_sees_cursor_via_context_var(
        self, mock_mixin: SyncRawMixin, mock_port_client: MagicMock
    ) -> None:
        from port_ocean.core.incremental.cursor_context import active_incremental_cursor

        configure_app_config(mock_mixin, ["issue"])
        register_incremental_handler(mock_mixin, kind="issue")
        captured: dict[str, datetime | None] = {"cursor": None}

        async def capture_cursor(
            resource: Any, index: int, user_agent_type: Any
        ) -> tuple[list[Any], list[Any]]:
            captured["cursor"] = active_incremental_cursor()
            return [], []

        mock_mixin.process_resource.side_effect = capture_cursor  # type: ignore[attr-defined]

        with patch("port_ocean.core.integrations.mixins.sync_raw.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            mock_ocean.config.integration.identifier = "test-integration"
            mock_ocean.config.integration.type = "fake-integration"
            await mock_mixin.sync_incremental(interval_seconds=900)

        assert captured["cursor"] is not None


class TestSyncIncrementalFailure:
    async def test_saves_cursor_after_successful_process(
        self, mock_mixin: SyncRawMixin, mock_port_client: MagicMock
    ) -> None:
        configure_app_config(mock_mixin, ["issue"])
        register_incremental_handler(mock_mixin, kind="issue")

        with patch("port_ocean.core.integrations.mixins.sync_raw.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            mock_ocean.config.integration.identifier = "test-integration"
            mock_ocean.config.integration.type = "fake-integration"
            await mock_mixin.sync_incremental(interval_seconds=900)

        mock_port_client.upsert_integration_cursor.assert_called_once()

    async def test_does_not_save_cursor_on_failure(
        self, mock_mixin: SyncRawMixin, mock_port_client: MagicMock
    ) -> None:
        configure_app_config(mock_mixin, ["issue"])
        register_incremental_handler(mock_mixin, kind="issue")
        mock_mixin.process_resource.side_effect = RuntimeError("error")  # type: ignore[attr-defined]

        with patch("port_ocean.core.integrations.mixins.sync_raw.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            mock_ocean.config.integration.identifier = "test-integration"
            mock_ocean.config.integration.type = "fake-integration"
            await mock_mixin.sync_incremental(interval_seconds=900)

        mock_mixin.process_resource.assert_called_once()  # type: ignore[attr-defined]
        mock_port_client.upsert_integration_cursor.assert_not_called()

    async def test_stops_remaining_kinds_when_one_fails(
        self, mock_mixin: SyncRawMixin, mock_port_client: MagicMock
    ) -> None:
        configure_app_config(mock_mixin, ["issue", "pull-request"])
        register_incremental_handler(mock_mixin, kind="issue")
        register_incremental_handler(mock_mixin, kind="pull-request")
        mock_mixin.process_resource.side_effect = RuntimeError("error")  # type: ignore[attr-defined]

        with patch("port_ocean.core.integrations.mixins.sync_raw.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            mock_ocean.config.integration.identifier = "test-integration"
            mock_ocean.config.integration.type = "fake-integration"
            await mock_mixin.sync_incremental(interval_seconds=900)

        # First kind failed — second kind was never attempted
        mock_mixin.process_resource.assert_called_once()  # type: ignore[attr-defined]
        mock_port_client.upsert_integration_cursor.assert_not_called()


class TestEventType:
    def test_incremental_event_type_value(self) -> None:
        assert EventType.INCREMENTAL_RESYNC == "incremental_resync"


class TestSyncIncrementalDspLifecycle:
    async def test_notifies_lifecycle_with_incremental_sync_type_when_dsp_enabled(
        self, mock_mixin: SyncRawMixin, mock_port_client: MagicMock
    ) -> None:
        configure_app_config(mock_mixin, ["issue"])
        register_incremental_handler(mock_mixin, kind="issue")
        lifecycle_client = MagicMock()
        lifecycle_client.notify_resync_started = AsyncMock()
        lifecycle_client.notify_resync_finished = AsyncMock()
        lifecycle_client.notify_resync_failed = AsyncMock()

        with (
            patch(
                "port_ocean.core.integrations.mixins.sync_raw.is_dsp_mode_enabled",
                new=AsyncMock(return_value=True),
            ),
            patch("port_ocean.core.integrations.mixins.sync_raw.ocean") as mock_ocean,
        ):
            mock_ocean.port_client = mock_port_client
            mock_ocean.config.integration.identifier = "test-integration"
            mock_ocean.config.integration.type = "fake-integration"
            mock_ocean.app.lifecycle_client = lifecycle_client
            await mock_mixin.sync_incremental(interval_seconds=900)

        lifecycle_client.notify_resync_started.assert_called_once()
        started_kwargs = lifecycle_client.notify_resync_started.call_args.kwargs
        assert started_kwargs["sync_type"] == SYNC_TYPE_INCREMENTAL_RESYNC
        assert started_kwargs["integration_id"] == "test-integration"
        lifecycle_client.notify_resync_finished.assert_called_once()
        finished_kwargs = lifecycle_client.notify_resync_finished.call_args.kwargs
        assert finished_kwargs["sync_type"] == SYNC_TYPE_INCREMENTAL_RESYNC
        lifecycle_client.notify_resync_failed.assert_not_called()

    async def test_skips_lifecycle_when_dsp_disabled(
        self, mock_mixin: SyncRawMixin, mock_port_client: MagicMock
    ) -> None:
        configure_app_config(mock_mixin, ["issue"])
        register_incremental_handler(mock_mixin, kind="issue")
        lifecycle_client = MagicMock()
        lifecycle_client.notify_resync_started = AsyncMock()
        lifecycle_client.notify_resync_finished = AsyncMock()
        lifecycle_client.notify_resync_failed = AsyncMock()

        with (
            patch(
                "port_ocean.core.integrations.mixins.sync_raw.is_dsp_mode_enabled",
                new=AsyncMock(return_value=False),
            ),
            patch("port_ocean.core.integrations.mixins.sync_raw.ocean") as mock_ocean,
        ):
            mock_ocean.port_client = mock_port_client
            mock_ocean.config.integration.identifier = "test-integration"
            mock_ocean.config.integration.type = "fake-integration"
            mock_ocean.app.lifecycle_client = lifecycle_client
            await mock_mixin.sync_incremental(interval_seconds=900)

        lifecycle_client.notify_resync_started.assert_not_called()
        lifecycle_client.notify_resync_finished.assert_not_called()
        lifecycle_client.notify_resync_failed.assert_not_called()


class TestIncrementalKindLifecycle:
    async def test_process_resource_notifies_kind_lifecycle_when_dsp_enabled(
        self, mock_mixin: SyncRawMixin, mock_port_client: MagicMock
    ) -> None:
        resource = make_resource_config("issue")
        mock_mixin._register_in_batches = AsyncMock(return_value=([], []))  # type: ignore[method-assign]
        lifecycle_client = MagicMock()
        lifecycle_client.notify_started = AsyncMock()
        lifecycle_client.notify_finished = AsyncMock()
        lifecycle_client.notify_failed = AsyncMock()
        lifecycle_client.notify_aborted = AsyncMock()

        with (
            patch(
                "port_ocean.core.integrations.mixins.sync_raw.is_dsp_mode_enabled",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "port_ocean.core.integrations.mixins.sync_raw.start_monitoring",
                new=AsyncMock(),
            ),
            patch(
                "port_ocean.core.integrations.mixins.sync_raw.stop_monitoring",
                new=AsyncMock(),
            ),
            patch(
                "port_ocean.core.integrations.mixins.sync_raw.start_kind_tracking",
            ),
            patch(
                "port_ocean.core.integrations.mixins.sync_raw.stop_kind_tracking",
            ),
            patch("port_ocean.core.integrations.mixins.sync_raw.ocean") as mock_ocean,
        ):
            mock_ocean.port_client = mock_port_client
            mock_ocean.config.integration.identifier = "test-integration"
            mock_ocean.config.integration.type = "fake-integration"
            mock_ocean.app.lifecycle_client = lifecycle_client
            mock_ocean.metrics.event_id = "incremental-resync-id"
            mock_ocean.metrics.sync_state = SyncState.SYNCING

            async with event_context(
                EventType.INCREMENTAL_RESYNC, trigger_type="machine"
            ) as evt:
                evt.port_app_config = make_port_app_config(["issue"])
                await mock_mixin._process_resource(
                    resource, index=0, user_agent_type=MagicMock()
                )

        lifecycle_client.notify_started.assert_called_once_with(
            event_id="incremental-resync-id",
            integration_id="test-integration",
            integration_type="fake-integration",
            granularity=GranularityType.KIND,
            kind_identifier="issue-0",
        )
        lifecycle_client.notify_finished.assert_called_once_with(
            event_id="incremental-resync-id",
            integration_type="fake-integration",
            granularity=GranularityType.KIND,
            kind_identifier="issue-0",
        )
        lifecycle_client.notify_failed.assert_not_called()

    async def test_sync_incremental_sets_metrics_event_id(
        self, mock_mixin: SyncRawMixin, mock_port_client: MagicMock
    ) -> None:
        configure_app_config(mock_mixin, ["issue"])
        register_incremental_handler(mock_mixin, kind="issue")

        with patch("port_ocean.core.integrations.mixins.sync_raw.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            mock_ocean.config.integration.identifier = "test-integration"
            mock_ocean.config.integration.type = "fake-integration"
            mock_ocean.metrics.event_id = ""
            await mock_mixin.sync_incremental(interval_seconds=900)

        assert mock_ocean.metrics.event_id != ""


class TestEventsMixinIncrementalRegistration:
    def test_on_incremental_resync_registers_handler(self) -> None:
        from port_ocean.core.integrations.mixins.events import EventsMixin

        mixin = EventsMixin()

        async def handler(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
            yield [{"id": "1"}]

        mixin.on_incremental_resync(handler, kind="issue")
        assert handler in mixin.event_strategy["incremental"]["issue"]

    def test_on_incremental_resync_registers_catch_all_handler(self) -> None:
        from port_ocean.core.integrations.mixins.events import EventsMixin

        mixin = EventsMixin()

        async def handler(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
            yield [{"id": "1"}]

        mixin.on_incremental_resync(handler, kind=None)
        assert handler in mixin.event_strategy["incremental"][None]

    def test_on_incremental_resync_ignores_none_function(self) -> None:
        from port_ocean.core.integrations.mixins.events import EventsMixin

        mixin = EventsMixin()
        result = mixin.on_incremental_resync(None, kind="issue")
        assert result is None
        assert len(mixin.event_strategy["incremental"]["issue"]) == 0

    def test_available_incremental_kinds_returns_registered_kinds(self) -> None:
        from port_ocean.core.integrations.mixins.events import EventsMixin

        mixin = EventsMixin()

        async def handler(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
            yield [{"id": "1"}]

        mixin.on_incremental_resync(handler, kind="issue")
        mixin.on_incremental_resync(handler, kind="pull-request")
        assert set(mixin.available_incremental_kinds) == {"issue", "pull-request"}
