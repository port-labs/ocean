"""Unit tests for IntegrationEventsReporter."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from port_ocean.core.integrations.reporters.integration_events import (
    BatchTimer,
    ExtractMetrics,
    IntegrationEventsReporter,
    KindToBlueprint,
    make_batch_id,
)


@pytest.fixture
def mock_auth() -> MagicMock:
    auth = MagicMock()
    auth.headers = AsyncMock(return_value={"Authorization": "Bearer test-token"})
    auth.integration_identifier = "test-integration"
    return auth


@pytest.fixture
def mock_ocean_context() -> MagicMock:
    """Patch the ocean context so OceanAsyncClient can be instantiated in tests."""
    with patch(
        "port_ocean.helpers.async_client.ocean"
    ) as mock_ocean:
        mock_ocean.config.ssl.third_party = MagicMock(
            enabled=False, allow_insecure=True
        )
        mock_ocean.app.is_saas.return_value = False
        yield mock_ocean


@pytest.fixture
def reporter(mock_auth: MagicMock, mock_ocean_context: MagicMock) -> IntegrationEventsReporter:
    return IntegrationEventsReporter(
        auth=mock_auth,
        integration_identifier="test-integration",
        integration_type="github",
        integration_version="1.0.0",
    )


@pytest.fixture
def kind_to_blueprint() -> KindToBlueprint:
    return KindToBlueprint(
        kind="pull-request",
        blueprint="githubPullRequest",
        kind_identifier="pull-request-0",
    )


class TestKindToBlueprint:
    def test_to_dict(self, kind_to_blueprint: KindToBlueprint) -> None:
        result = kind_to_blueprint.to_dict()
        assert result == {
            "kind": "pull-request",
            "blueprint": "githubPullRequest",
            "kindIdentifier": "pull-request-0",
        }


class TestExtractMetrics:
    def test_to_dict(self) -> None:
        metrics = ExtractMetrics(fetched=42, failed=2, duration_seconds=1.5678)
        result = metrics.to_dict()
        assert result == {
            "extract": {
                "fetched": 42,
                "failed": 2,
                "durationSeconds": 1.568,
            }
        }

    def test_to_dict_defaults(self) -> None:
        metrics = ExtractMetrics()
        result = metrics.to_dict()
        assert result == {
            "extract": {
                "fetched": 0,
                "failed": 0,
                "durationSeconds": 0.0,
            }
        }


class TestBatchTimer:
    def test_elapsed_seconds(self) -> None:
        timer = BatchTimer()
        elapsed = timer.elapsed_seconds()
        assert elapsed >= 0
        assert elapsed < 1.0


class TestMakeBatchId:
    def test_returns_unique_ids(self) -> None:
        ids = {make_batch_id() for _ in range(100)}
        assert len(ids) == 100

    def test_returns_string(self) -> None:
        batch_id = make_batch_id()
        assert isinstance(batch_id, str)
        assert len(batch_id) > 0


class TestEventConstruction:
    def test_build_event_fields(self, reporter: IntegrationEventsReporter) -> None:
        ev = reporter._build_event(
            granularity="KIND",
            lifecycle="STARTED",
            correlation_id="sync-123",
            payload={"kindToBlueprint": {"kind": "pr", "blueprint": "bp", "kindIdentifier": "pr-0"}},
            event_id="sync-123#pr-0#KIND#STARTED",
        )

        assert ev["granularity"] == "KIND"
        assert ev["lifecycle"] == "STARTED"
        assert ev["source"] == "OCEAN"
        assert ev["correlationId"] == "sync-123"
        assert ev["correlationKind"] == "INCREMENTAL_RESYNC"
        assert ev["integrationIdentifier"] == "test-integration"
        assert ev["integrationType"] == "github"
        assert ev["integrationVersion"] == "1.0.0"
        assert ev["id"] == "sync-123#pr-0#KIND#STARTED"
        assert "payload" in ev
        assert "timestamp" in ev


class TestURLDerivation:
    async def test_derives_events_url_from_log_url(
        self, reporter: IntegrationEventsReporter
    ) -> None:
        with patch("port_ocean.context.ocean.ocean") as mock_ocean:
            mock_ocean.port_client.get_log_attributes = AsyncMock(
                return_value={"ingestUrl": "https://ingest.getport.io/logs/integration/abc123"}
            )
            url = await reporter._get_events_ingest_url()

        assert url == "https://ingest.getport.io/events/ingestId/abc123"

    async def test_caches_events_url(
        self, reporter: IntegrationEventsReporter
    ) -> None:
        with patch("port_ocean.context.ocean.ocean") as mock_ocean:
            mock_ocean.port_client.get_log_attributes = AsyncMock(
                return_value={"ingestUrl": "https://ingest.getport.io/logs/integration/xyz"}
            )
            url1 = await reporter._get_events_ingest_url()
            url2 = await reporter._get_events_ingest_url()

        assert url1 == url2
        mock_ocean.port_client.get_log_attributes.assert_called_once()


class TestBuffering:
    async def test_flush_posts_buffered_events(
        self, reporter: IntegrationEventsReporter
    ) -> None:
        reporter._post = AsyncMock()  # type: ignore[method-assign]

        await reporter._enqueue({"test": "event1"})
        await reporter._enqueue({"test": "event2"})
        assert len(reporter._buffer) == 2

        await reporter.flush()
        assert len(reporter._buffer) == 0
        reporter._post.assert_called_once_with(
            [{"test": "event1"}, {"test": "event2"}],
        )

    async def test_flush_noop_when_empty(
        self, reporter: IntegrationEventsReporter
    ) -> None:
        reporter._post = AsyncMock()  # type: ignore[method-assign]
        await reporter.flush()
        reporter._post.assert_not_called()

    async def test_auto_flush_on_threshold(
        self, reporter: IntegrationEventsReporter
    ) -> None:
        reporter._post = AsyncMock()  # type: ignore[method-assign]

        for i in range(10):
            await reporter._enqueue({"idx": i})

        reporter._post.assert_called_once()
        assert len(reporter._buffer) == 0


class TestErrorResilience:
    async def test_flush_swallows_http_errors(
        self, reporter: IntegrationEventsReporter
    ) -> None:
        reporter._post = AsyncMock(side_effect=RuntimeError("network error"))  # type: ignore[method-assign]

        await reporter._enqueue({"test": "event"})
        # Should not raise
        await reporter.flush()
        assert len(reporter._buffer) == 0

    async def test_report_kind_started_does_not_raise_on_failure(
        self, reporter: IntegrationEventsReporter, kind_to_blueprint: KindToBlueprint
    ) -> None:
        reporter._post = AsyncMock(side_effect=RuntimeError("fail"))  # type: ignore[method-assign]

        # Should not raise
        await reporter.report_kind_started(
            correlation_id="sync-1",
            kind_to_blueprint=kind_to_blueprint,
            kind_index=0,
        )


class TestKindEvents:
    async def test_report_kind_started_enqueues_event(
        self, reporter: IntegrationEventsReporter, kind_to_blueprint: KindToBlueprint
    ) -> None:
        reporter._post = AsyncMock()  # type: ignore[method-assign]

        await reporter.report_kind_started(
            correlation_id="sync-abc",
            kind_to_blueprint=kind_to_blueprint,
            kind_index=0,
        )
        assert len(reporter._buffer) == 1
        ev = reporter._buffer[0]
        assert ev["granularity"] == "KIND"
        assert ev["lifecycle"] == "STARTED"
        assert ev["id"] == "sync-abc#pull-request-0#KIND#STARTED"
        assert ev["payload"]["kindToBlueprint"]["kindIdentifier"] == "pull-request-0"
        assert ev["payload"]["kindIndex"] == 0

    async def test_report_kind_ended_flushes_and_posts(
        self, reporter: IntegrationEventsReporter, kind_to_blueprint: KindToBlueprint
    ) -> None:
        reporter._post = AsyncMock()  # type: ignore[method-assign]

        # Add a pending batch event first
        await reporter._enqueue({"test": "batch-event"})

        await reporter.report_kind_ended(
            correlation_id="sync-abc",
            kind_to_blueprint=kind_to_blueprint,
            kind_index=0,
        )

        # Should have flushed all events (batch flush + kind ended post)
        assert len(reporter._buffer) == 0
        assert reporter._post.call_count == 2
        # Second call is the KIND ENDED event posted directly
        last_call_events = reporter._post.call_args_list[1][0][0]
        assert last_call_events[0]["granularity"] == "KIND"
        assert last_call_events[0]["lifecycle"] == "ENDED"
        assert last_call_events[0]["id"] == "sync-abc#pull-request-0#KIND#ENDED"


class TestBatchEvents:
    async def test_report_batch_started(
        self, reporter: IntegrationEventsReporter
    ) -> None:
        reporter._post = AsyncMock()  # type: ignore[method-assign]

        await reporter.report_batch_started(
            correlation_id="sync-abc",
            batch_id="batch-001",
            kind_identifier="pull-request-0",
        )

        assert len(reporter._buffer) == 1
        ev = reporter._buffer[0]
        assert ev["granularity"] == "BATCH"
        assert ev["lifecycle"] == "STARTED"
        assert ev["id"] == "batch-001#BATCH#STARTED"
        assert ev["payload"]["batchId"] == "batch-001"
        assert ev["payload"]["kindIdentifier"] == "pull-request-0"

    async def test_report_batch_ended_with_metrics(
        self, reporter: IntegrationEventsReporter
    ) -> None:
        reporter._post = AsyncMock()  # type: ignore[method-assign]

        metrics = ExtractMetrics(fetched=50, failed=1, duration_seconds=2.5)
        await reporter.report_batch_ended(
            correlation_id="sync-abc",
            batch_id="batch-001",
            kind_identifier="pull-request-0",
            metrics=metrics,
        )

        assert len(reporter._buffer) == 1
        ev = reporter._buffer[0]
        assert ev["granularity"] == "BATCH"
        assert ev["lifecycle"] == "ENDED"
        assert ev["id"] == "batch-001#BATCH#ENDED"
        assert ev["payload"]["batchId"] == "batch-001"
        assert ev["payload"]["kindIdentifier"] == "pull-request-0"
        assert ev["payload"]["metrics"]["extract"]["fetched"] == 50
        assert ev["payload"]["metrics"]["extract"]["failed"] == 1
        assert ev["payload"]["metrics"]["extract"]["durationSeconds"] == 2.5
        assert ev["payload"]["pendingUpsertIds"] == []
