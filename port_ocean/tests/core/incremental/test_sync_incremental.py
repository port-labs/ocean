"""Unit tests for SyncRawMixin.sync_incremental and the retry helper."""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    mixin._port_app_config_handler = MagicMock()
    mixin.process_resource = AsyncMock()  # type: ignore[method-assign]
    return mixin


def configure_app_config(mixin: SyncRawMixin, kinds: list[str]) -> PortAppConfig:
    config = make_port_app_config(kinds)

    async def get_config(use_cache: bool = True) -> PortAppConfig:
        return config

    mixin._port_app_config_handler.get_port_app_config = get_config
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
            await mock_mixin.sync_incremental(interval_seconds=900)
        after = datetime.now(timezone.utc)

        mock_port_client.upsert_integration_cursor.assert_called_once()
        # The persisted cursor is tick_started_at (snapshotted before the fetch).
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
            await mock_mixin.sync_incremental(interval_seconds=900)

        mock_port_client.upsert_integration_cursor.assert_called_once()


class TestSyncIncrementalFailure:
    async def test_saves_cursor_after_successful_process(
        self, mock_mixin: SyncRawMixin, mock_port_client: MagicMock
    ) -> None:
        configure_app_config(mock_mixin, ["issue"])
        register_incremental_handler(mock_mixin, kind="issue")

        with patch("port_ocean.core.integrations.mixins.sync_raw.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            mock_ocean.config.integration.identifier = "test-integration"
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
            await mock_mixin.sync_incremental(interval_seconds=900)

        # First kind failed — second kind was never attempted
        mock_mixin.process_resource.assert_called_once()  # type: ignore[attr-defined]
        mock_port_client.upsert_integration_cursor.assert_not_called()


class TestSyncIncrementalSelfLoop:
    async def test_exits_after_one_tick_when_elapsed_less_than_interval(
        self, mock_mixin: SyncRawMixin, mock_port_client: MagicMock
    ) -> None:
        configure_app_config(mock_mixin, ["issue"])
        register_incremental_handler(mock_mixin, kind="issue")

        with patch("port_ocean.core.integrations.mixins.sync_raw.ocean") as mock_ocean:
            mock_ocean.port_client = mock_port_client
            mock_ocean.config.integration.identifier = "test-integration"
            await mock_mixin.sync_incremental(interval_seconds=9999)

        # process_resource called exactly once (one tick, no self-loop)
        mock_mixin.process_resource.assert_called_once()  # type: ignore[attr-defined]

    async def test_self_loops_when_tick_exceeds_interval(
        self, mock_mixin: SyncRawMixin, mock_port_client: MagicMock
    ) -> None:
        configure_app_config(mock_mixin, ["issue"])
        register_incremental_handler(mock_mixin, kind="issue")

        tick_count = 0

        async def slow_process(resource: Any, index: int, user_agent_type: Any) -> None:
            nonlocal tick_count
            tick_count += 1

        mock_mixin.process_resource.side_effect = slow_process  # type: ignore[attr-defined]

        # Use interval=0 so elapsed always exceeds the interval — but cap at 2 ticks
        # by having the third tick return immediately without work (no more resources).
        with patch("port_ocean.core.integrations.mixins.sync_raw.datetime") as mock_dt:
            # First call (tick_started_at) returns T0.
            # Second call (elapsed check) returns T0 + 1h so elapsed > interval=1s.
            # Third call (tick_started_at again) returns T1.
            # Fourth call (elapsed check) returns T1 + 0s so elapsed < interval.
            t0 = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
            t1 = t0 + timedelta(hours=1)
            mock_dt.now.side_effect = [t0, t0 + timedelta(hours=2), t1, t1]
            mock_dt.fromisoformat = datetime.fromisoformat

            with patch(
                "port_ocean.core.integrations.mixins.sync_raw.ocean"
            ) as mock_ocean:
                mock_ocean.port_client = mock_port_client
                mock_ocean.config.integration.identifier = "test-integration"
                await mock_mixin.sync_incremental(interval_seconds=1)

        assert tick_count == 2


class TestEventType:
    def test_incremental_event_type_value(self) -> None:
        assert EventType.INCREMENTAL_RESYNC == "incremental_resync"


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
