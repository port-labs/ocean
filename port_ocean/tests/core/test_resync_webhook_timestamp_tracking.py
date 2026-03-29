"""
Comprehensive tests for resync and webhook timestamp and event type tracking.
Tests verify the implementation of resync_start_time and event_type columns.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.core.models import LakehouseEventType, LakehouseOperation
from port_ocean.clients.port.mixins.integrations import IntegrationClientMixin


class TestLakehouseEventTypeEnum:
    """Test suite for LakehouseEventType enum"""

    def test_enum_values_are_correct(self) -> None:
        """Verify enum values match specification"""
        assert LakehouseEventType.RESYNC.value == "resync"
        assert LakehouseEventType.LIVE_EVENT.value == "live-event"

    def test_enum_values_are_strings(self) -> None:
        """Verify enum values can be compared as strings"""
        assert LakehouseEventType.RESYNC == "resync"
        assert LakehouseEventType.LIVE_EVENT == "live-event"

    def test_enum_values_are_distinct(self) -> None:
        """Verify RESYNC and LIVE_EVENT are different"""
        assert LakehouseEventType.RESYNC != LakehouseEventType.LIVE_EVENT
        assert LakehouseEventType.RESYNC.value != LakehouseEventType.LIVE_EVENT.value

    def test_enum_iteration(self) -> None:
        """Verify all enum members can be iterated"""
        event_types = list(LakehouseEventType)
        assert len(event_types) == 2
        assert LakehouseEventType.RESYNC in event_types
        assert LakehouseEventType.LIVE_EVENT in event_types


class TestPostIntegrationRawDataInputValidation:
    """Test input validation in post_integration_raw_data"""

    @pytest.mark.asyncio
    async def test_empty_sync_id_raises_error(self) -> None:
        """Verify empty sync_id raises ValueError"""
        mixin = IntegrationClientMixin(
            integration_identifier="test-integration",
            integration_version="1.0.0",
            auth=MagicMock(),
            client=MagicMock(),
        )

        with pytest.raises(ValueError, match="sync_id cannot be empty"):
            await mixin.post_integration_raw_data(
                raw_data=[{"test": "data"}],
                sync_id="",  # Empty - should fail
                kind="repository",
            )

    @pytest.mark.asyncio
    async def test_empty_kind_raises_error(self) -> None:
        """Verify empty kind raises ValueError"""
        mixin = IntegrationClientMixin(
            integration_identifier="test-integration",
            integration_version="1.0.0",
            auth=MagicMock(),
            client=MagicMock(),
        )

        with pytest.raises(ValueError, match="kind cannot be empty"):
            await mixin.post_integration_raw_data(
                raw_data=[{"test": "data"}],
                sync_id="test-sync-123",
                kind="",  # Empty - should fail
            )

    @pytest.mark.asyncio
    async def test_future_resync_start_time_raises_error(self) -> None:
        """Verify future timestamp raises ValueError"""
        mixin = IntegrationClientMixin(
            integration_identifier="test-integration",
            integration_version="1.0.0",
            auth=MagicMock(),
            client=MagicMock(),
        )
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)

        with pytest.raises(ValueError, match="cannot be in the future"):
            await mixin.post_integration_raw_data(
                raw_data=[{"test": "data"}],
                sync_id="test-sync-123",
                kind="repository",
                resync_start_time=future_time,  # Future - should fail
            )

    @pytest.mark.asyncio
    async def test_past_resync_start_time_succeeds(self) -> None:
        """Verify past timestamp is accepted"""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
        mock_auth = MagicMock()
        mock_auth.headers = AsyncMock(return_value={})
        mock_auth.ingest_url = "https://test.example.com"
        mock_auth.integration_type = "test"

        mixin = IntegrationClientMixin(
            integration_identifier="test-integration",
            integration_version="1.0.0",
            auth=mock_auth,
            client=mock_client,
        )

        past_time = datetime.now(timezone.utc) - timedelta(hours=1)

        # Should not raise
        with patch(
            "port_ocean.clients.port.mixins.integrations.handle_port_status_code"
        ):
            await mixin.post_integration_raw_data(
                raw_data=[{"test": "data"}],
                sync_id="test-sync-123",
                kind="repository",
                resync_start_time=past_time,
                event_type=LakehouseEventType.RESYNC,
            )

    @pytest.mark.asyncio
    async def test_timezone_naive_future_timestamp_raises_error(self) -> None:
        """Verify timezone-naive future timestamp raises ValueError (tests timezone.utc fallback)"""
        mixin = IntegrationClientMixin(
            integration_identifier="test-integration",
            integration_version="1.0.0",
            auth=MagicMock(),
            client=MagicMock(),
        )

        # Timezone-naive datetime far in the future (no tzinfo)
        # This tests that the code properly handles naive datetimes
        future_time_naive = datetime(2099, 12, 31, 23, 59, 59)

        with pytest.raises(ValueError, match="cannot be in the future"):
            await mixin.post_integration_raw_data(
                raw_data=[{"test": "data"}],
                sync_id="test-sync-123",
                kind="repository",
                resync_start_time=future_time_naive,
            )

    @pytest.mark.asyncio
    async def test_timezone_naive_past_timestamp_succeeds(self) -> None:
        """Verify timezone-naive past timestamp is accepted (tests timezone.utc fallback)"""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
        mock_auth = MagicMock()
        mock_auth.headers = AsyncMock(return_value={})
        mock_auth.ingest_url = "https://test.example.com"
        mock_auth.integration_type = "test"

        mixin = IntegrationClientMixin(
            integration_identifier="test-integration",
            integration_version="1.0.0",
            auth=mock_auth,
            client=mock_client,
        )

        # Timezone-naive datetime in the past (no tzinfo)
        # This tests that the code properly handles naive datetimes
        past_time_naive = datetime(2020, 1, 1, 0, 0, 0)

        # Should not raise - naive datetime treated as UTC
        with patch(
            "port_ocean.clients.port.mixins.integrations.handle_port_status_code"
        ):
            await mixin.post_integration_raw_data(
                raw_data=[{"test": "data"}],
                sync_id="test-sync-123",
                kind="repository",
                resync_start_time=past_time_naive,
                event_type=LakehouseEventType.RESYNC,
            )


class TestPostIntegrationRawDataRequestBody:
    """Test request body construction in post_integration_raw_data"""

    @pytest.mark.asyncio
    async def test_request_body_with_resync_event_type(self) -> None:
        """Verify request body includes resyncStartTime and eventType for resync"""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
        mock_auth = MagicMock()
        mock_auth.headers = AsyncMock(return_value={"Authorization": "Bearer test"})
        mock_auth.ingest_url = "https://test.example.com"
        mock_auth.integration_type = "github"

        mixin = IntegrationClientMixin(
            integration_identifier="test-integration-123",
            integration_version="1.0.0",
            auth=mock_auth,
            client=mock_client,
        )

        resync_time = datetime(2024, 3, 29, 10, 0, 0, tzinfo=timezone.utc)
        raw_data = [{"name": "test-repo", "stars": 100}]

        with patch(
            "port_ocean.clients.port.mixins.integrations.handle_port_status_code"
        ):
            await mixin.post_integration_raw_data(
                raw_data=raw_data,
                sync_id="resync-abc-123",
                kind="repository",
                operation=LakehouseOperation.UPSERT,
                resync_start_time=resync_time,
                event_type=LakehouseEventType.RESYNC,
            )

        # Verify the call was made
        assert mock_client.post.called
        call_args = mock_client.post.call_args

        # Verify the request body
        request_body = call_args.kwargs["json"]
        assert request_body["items"] == raw_data
        assert request_body["operation"] == "upsert"
        assert request_body["eventType"] == "resync"
        assert request_body["resyncStartTime"] == resync_time.isoformat()
        assert request_body["eventType"] == "resync"
        assert "extractionTimestamp" in request_body

    @pytest.mark.asyncio
    async def test_request_body_with_live_event_type(self) -> None:
        """Verify request body includes resyncStartTime and eventType for webhook"""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
        mock_auth = MagicMock()
        mock_auth.headers = AsyncMock(return_value={"Authorization": "Bearer test"})
        mock_auth.ingest_url = "https://test.example.com"
        mock_auth.integration_type = "github"

        mixin = IntegrationClientMixin(
            integration_identifier="test-integration-123",
            integration_version="1.0.0",
            auth=mock_auth,
            client=mock_client,
        )

        webhook_time = datetime(2024, 3, 29, 10, 30, 0, tzinfo=timezone.utc)
        raw_data = [{"name": "updated-repo", "stars": 150}]

        with patch(
            "port_ocean.clients.port.mixins.integrations.handle_port_status_code"
        ):
            await mixin.post_integration_raw_data(
                raw_data=raw_data,
                sync_id="webhook-xyz-789",
                kind="repository",
                operation=LakehouseOperation.UPSERT,
                resync_start_time=webhook_time,
                event_type=LakehouseEventType.LIVE_EVENT,
            )

        # Verify the call was made
        assert mock_client.post.called
        call_args = mock_client.post.call_args

        # Verify the request body
        request_body = call_args.kwargs["json"]
        assert request_body["items"] == raw_data
        assert request_body["operation"] == "upsert"
        assert request_body["eventType"] == "live-event"
        assert request_body["resyncStartTime"] == webhook_time.isoformat()
        assert request_body["eventType"] == "live-event"

    @pytest.mark.asyncio
    async def test_request_body_without_optional_params(self) -> None:
        """Verify request body works without resync_start_time and event_type"""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
        mock_auth = MagicMock()
        mock_auth.headers = AsyncMock(return_value={"Authorization": "Bearer test"})
        mock_auth.ingest_url = "https://test.example.com"
        mock_auth.integration_type = "github"

        mixin = IntegrationClientMixin(
            integration_identifier="test-integration-123",
            integration_version="1.0.0",
            auth=mock_auth,
            client=mock_client,
        )

        raw_data = [{"name": "test-repo"}]

        with patch(
            "port_ocean.clients.port.mixins.integrations.handle_port_status_code"
        ):
            await mixin.post_integration_raw_data(
                raw_data=raw_data,
                sync_id="test-sync-123",
                kind="repository",
                # No resync_start_time or event_type
            )

        # Verify the call was made
        assert mock_client.post.called
        call_args = mock_client.post.call_args

        # Verify the request body does NOT include optional fields, but includes default eventType
        request_body = call_args.kwargs["json"]
        assert "resyncStartTime" not in request_body
        assert request_body["eventType"] == "live-event"


class TestWebhookEventTimestampTracking:
    """Test WebhookEvent created_at timestamp tracking"""

    @pytest.mark.asyncio
    async def test_webhook_event_from_request_sets_created_at(self) -> None:
        """Verify WebhookEvent.from_request() sets created_at"""
        from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        mock_request.json = AsyncMock(return_value={"event": "push", "repo": "test"})
        mock_request.headers = {"x-github-event": "push"}

        before = datetime.now(timezone.utc)
        webhook_event = await WebhookEvent.from_request(mock_request)
        after = datetime.now(timezone.utc)

        # Verify created_at is set and within expected range
        assert webhook_event.created_at is not None
        assert isinstance(webhook_event.created_at, datetime)
        assert before <= webhook_event.created_at <= after
        assert webhook_event.created_at.tzinfo == timezone.utc

    def test_webhook_event_from_dict_parses_created_at(self) -> None:
        """Verify WebhookEvent.from_dict() parses created_at from ISO string"""
        from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

        timestamp = "2026-03-29T10:00:00+00:00"
        data = {
            "trace_id": "test-trace-123",
            "payload": {"event": "push"},
            "headers": {},
            "created_at": timestamp,
        }

        webhook_event = WebhookEvent.from_dict(data)

        assert webhook_event.created_at is not None
        assert webhook_event.created_at == datetime.fromisoformat(timestamp)

    def test_webhook_event_from_dict_handles_missing_created_at(self) -> None:
        """Verify WebhookEvent.from_dict() generates timestamp if missing"""
        from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

        data = {
            "trace_id": "test-trace-123",
            "payload": {"event": "push"},
            "headers": {},
            # No created_at field
        }

        before = datetime.now(timezone.utc)
        webhook_event = WebhookEvent.from_dict(data)
        after = datetime.now(timezone.utc)

        # Should generate a timestamp
        assert webhook_event.created_at is not None
        assert before <= webhook_event.created_at <= after

    def test_webhook_event_clone_preserves_created_at(self) -> None:
        """Verify WebhookEvent.clone() preserves created_at"""
        from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

        original_time = datetime(2024, 3, 29, 10, 0, 0, tzinfo=timezone.utc)
        original = WebhookEvent(
            trace_id="test-123",
            payload={"event": "push"},
            headers={},
            created_at=original_time,
        )

        cloned = original.clone()

        assert cloned.created_at == original_time
        assert cloned.trace_id == original.trace_id

    def test_webhook_event_raw_results_has_created_at(self) -> None:
        """Verify WebhookEventRawResults stores created_at"""
        from port_ocean.core.handlers.webhook.webhook_event import (
            WebhookEventRawResults,
        )

        timestamp = datetime(2024, 3, 29, 11, 0, 0, tzinfo=timezone.utc)
        results = WebhookEventRawResults(
            updated_raw_results=[{"name": "repo"}],
            deleted_raw_results=[],
            created_at=timestamp,
        )

        assert results.created_at == timestamp

    def test_webhook_event_raw_results_generates_created_at_if_missing(self) -> None:
        """Verify WebhookEventRawResults generates timestamp if not provided"""
        from port_ocean.core.handlers.webhook.webhook_event import (
            WebhookEventRawResults,
        )

        before = datetime.now(timezone.utc)
        results = WebhookEventRawResults(
            updated_raw_results=[{"name": "repo"}],
            deleted_raw_results=[],
            # No created_at provided
        )
        after = datetime.now(timezone.utc)

        assert results.created_at is not None
        assert before <= results.created_at <= after


class TestTimestampConversionToMilliseconds:
    """Test datetime to unix milliseconds conversion"""

    def test_converts_datetime_to_unix_milliseconds(self) -> None:
        """Verify datetime converts to unix milliseconds correctly"""
        dt = datetime(2024, 3, 29, 10, 30, 45, 123456, tzinfo=timezone.utc)
        timestamp_ms = int(dt.timestamp() * 1000)

        # Verify it's a reasonable timestamp
        assert timestamp_ms > 1700000000000  # After Nov 2023
        assert timestamp_ms < 2000000000000  # Before 2033
        # Verify milliseconds component is preserved
        assert timestamp_ms % 1000 == 123  # 123 milliseconds from microseconds

    def test_milliseconds_precision_preserved(self) -> None:
        """Verify microseconds are converted to milliseconds correctly"""
        # 123456 microseconds = 123.456 milliseconds = 123 ms (truncated)
        dt = datetime(2026, 1, 1, 0, 0, 0, 123456, tzinfo=timezone.utc)
        timestamp_ms = int(dt.timestamp() * 1000)

        # Verify milliseconds component
        milliseconds_part = timestamp_ms % 1000
        assert milliseconds_part == 123


class TestBackwardCompatibility:
    """Test backward compatibility with existing code"""

    @pytest.mark.asyncio
    async def test_optional_params_can_be_omitted(self) -> None:
        """Verify resync_start_time and event_type can be omitted"""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
        mock_auth = MagicMock()
        mock_auth.headers = AsyncMock(return_value={})
        mock_auth.ingest_url = "https://test.example.com"
        mock_auth.integration_type = "test"

        mixin = IntegrationClientMixin(
            integration_identifier="test",
            integration_version="1.0.0",
            auth=mock_auth,
            client=mock_client,
        )

        # Should work without new parameters (backward compatible)
        with patch(
            "port_ocean.clients.port.mixins.integrations.handle_port_status_code"
        ):
            await mixin.post_integration_raw_data(
                raw_data=[{"test": "data"}],
                sync_id="sync-123",
                kind="repository",
                operation=LakehouseOperation.UPSERT,
            )

        assert mock_client.post.called

        # For backward compatibility:

        assert LakehouseEventType.RESYNC.value == "resync"
        assert LakehouseEventType.LIVE_EVENT.value == "live-event"
