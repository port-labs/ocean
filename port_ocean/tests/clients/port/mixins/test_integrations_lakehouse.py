from datetime import datetime, timezone
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch, AsyncMock

import httpx
import pytest

from port_ocean.clients.port.mixins.integrations import IntegrationClientMixin
from port_ocean.clients.port.retry_transport import TokenRetryTransport
from port_ocean.core.models import (
    LakehouseDataEntryBatch,
    LakehouseEventType,
    LakehouseOperation,
)
from port_ocean.context.event import EventType, event_context
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.helpers.retry import RetryConfig
from port_ocean.tests.helpers.lakehouse_batch import make_single_entry_lakehouse_batch

TEST_INTEGRATION_IDENTIFIER = "test-integration"
TEST_INTEGRATION_VERSION = "1.0.0"
TEST_INGEST_URL = "https://api.example.com"


@pytest.fixture(autouse=True)
def mock_ocean_context() -> Generator[MagicMock, None, None]:
    with patch("port_ocean.helpers.async_client.ocean") as mock_ocean:
        mock_ocean.app.is_saas = MagicMock(return_value=False)
        yield mock_ocean


def _inner_http_transport(http_client: OceanAsyncClient) -> httpx.AsyncHTTPTransport:
    transport = http_client._transport
    if hasattr(transport, "_wrapped"):
        transport = transport._wrapped
    assert isinstance(transport, TokenRetryTransport)
    inner = transport._wrapped_transport
    assert isinstance(inner, httpx.AsyncHTTPTransport)
    return inner


@pytest.fixture
def lakehouse_integration_client(monkeypatch: Any) -> IntegrationClientMixin:
    """Create an IntegrationClientMixin instance for lakehouse testing."""
    auth = MagicMock()
    auth.headers = AsyncMock()
    auth.headers.return_value = {"Authorization": "Bearer test-token"}
    auth.integration_type = "github"

    client = MagicMock()
    client.post = AsyncMock()
    client.post.return_value = MagicMock()
    client.post.return_value.status_code = 200
    client.post.return_value.is_error = False

    integration_client = IntegrationClientMixin(
        integration_identifier=TEST_INTEGRATION_IDENTIFIER,
        integration_version=TEST_INTEGRATION_VERSION,
        auth=auth,
        client=client,
    )
    monkeypatch.setattr(
        integration_client,
        "get_ingest_attributes",
        AsyncMock(return_value={"ingestUrl": TEST_INGEST_URL}),
    )

    return integration_client


async def test_post_integration_raw_data_default_operation(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test post_integration_raw_data_batch with default UPSERT operation."""
    raw_data = [{"name": "repo-one", "stars": 100}, {"name": "repo-two", "stars": 200}]
    sync_id = "test-sync-123"
    kind = "repository"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        event = make_single_entry_lakehouse_batch(raw_data, kind=kind, index=0)
        await lakehouse_integration_client.post_integration_raw_data_batch(
            sync_id, event
        )

        lakehouse_integration_client.client.post.assert_called_once()
        call_args = lakehouse_integration_client.client.post.call_args

        expected_url = f"{TEST_INGEST_URL}/lake/write/integration-type/github/integration/{TEST_INTEGRATION_IDENTIFIER}/sync/{sync_id}/kind/{kind}"
        assert call_args[0][0] == expected_url
        assert call_args[1]["extensions"] == {"retryable": True}

        body = call_args[1]["json"]
        assert body["kind"] == kind
        assert body["eventType"] == "live-event"
        assert body["extractionTimestamp"] == event["extraction_timestamp"]
        assert len(body["data"]) == 1
        entry = body["data"][0]
        assert entry["items"] == raw_data
        assert entry["request"] == {}
        assert entry["response"] == {}
        assert entry["metadata"]["operation"] == "upsert"
        assert entry["metadata"]["resourceIndex"] == 0
        assert entry["metadata"]["selectorHash"] is None
        assert "extractionTimestamp" in entry["metadata"]
        assert "resyncStartTime" not in body
        assert "eventId" not in body


async def test_post_integration_raw_data_with_upsert_operation(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test post_integration_raw_data_batch with explicit UPSERT operation."""
    raw_data = [{"id": "123", "name": "test"}]
    sync_id = "webhook-event-456"
    kind = "service"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        event = make_single_entry_lakehouse_batch(
            raw_data, kind=kind, index=0, operation=LakehouseOperation.UPSERT
        )
        await lakehouse_integration_client.post_integration_raw_data_batch(
            sync_id, event
        )

        lakehouse_integration_client.client.post.assert_called_once()
        call_args = lakehouse_integration_client.client.post.call_args

        body = call_args[1]["json"]
        assert body["kind"] == kind
        assert body["eventType"] == "live-event"
        entry = body["data"][0]
        assert entry["items"] == raw_data
        assert entry["metadata"]["operation"] == "upsert"
        assert entry["metadata"]["resourceIndex"] == 0


async def test_post_integration_raw_data_with_delete_operation(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test post_integration_raw_data_batch with DELETE operation."""
    raw_data = [{"id": "789"}]
    sync_id = "webhook-event-789"
    kind = "repository"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        event = make_single_entry_lakehouse_batch(
            raw_data, kind=kind, index=0, operation=LakehouseOperation.DELETE
        )
        await lakehouse_integration_client.post_integration_raw_data_batch(
            sync_id, event
        )

        lakehouse_integration_client.client.post.assert_called_once()
        call_args = lakehouse_integration_client.client.post.call_args

        body = call_args[1]["json"]
        assert body["kind"] == kind
        assert body["eventType"] == "live-event"
        entry = body["data"][0]
        assert entry["items"] == raw_data
        assert entry["metadata"]["operation"] == "delete"
        assert entry["metadata"]["resourceIndex"] == 0


async def test_post_integration_raw_data_url_construction(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test that post_integration_raw_data_batch constructs the correct URL."""
    raw_data = [{"test": "data"}]
    sync_id = "sync-abc-123"
    kind = "deployment"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        event = make_single_entry_lakehouse_batch(
            raw_data,
            kind=kind,
            index=2,
            operation=LakehouseOperation.UPSERT,
        )
        await lakehouse_integration_client.post_integration_raw_data_batch(
            sync_id, event
        )

        lakehouse_integration_client.client.post.assert_called_once()
        call_args = lakehouse_integration_client.client.post.call_args

        expected_url = (
            f"{TEST_INGEST_URL}/lake/write/"
            f"integration-type/github/"
            f"integration/{TEST_INTEGRATION_IDENTIFIER}/"
            f"sync/{sync_id}/"
            f"kind/{kind}"
        )
        assert call_args[0][0] == expected_url
        assert call_args[1]["json"]["data"][0]["metadata"]["resourceIndex"] == 2


async def test_post_integration_raw_data_empty_list(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test post_integration_raw_data_batch with empty raw data list."""
    raw_data: list = []
    sync_id = "sync-empty"
    kind = "repository"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        event = make_single_entry_lakehouse_batch(
            raw_data, kind=kind, index=0, operation=LakehouseOperation.DELETE
        )
        await lakehouse_integration_client.post_integration_raw_data_batch(
            sync_id, event
        )

        lakehouse_integration_client.client.post.assert_called_once()
        call_args = lakehouse_integration_client.client.post.call_args

        body = call_args[1]["json"]
        assert body["kind"] == kind
        assert body["eventType"] == "live-event"
        entry = body["data"][0]
        assert entry["items"] == []
        assert entry["metadata"]["operation"] == "delete"
        assert entry["metadata"]["resourceIndex"] == 0


async def test_post_integration_raw_data_extraction_timestamp(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test that post_integration_raw_data_batch includes extractionTimestamp."""
    raw_data = [{"name": "test"}]
    sync_id = "sync-timestamp-test"
    kind = "service"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        event = make_single_entry_lakehouse_batch(raw_data, kind=kind, index=0)
        await lakehouse_integration_client.post_integration_raw_data_batch(
            sync_id, event
        )

        lakehouse_integration_client.client.post.assert_called_once()
        call_args = lakehouse_integration_client.client.post.call_args

        body = call_args[1]["json"]
        root_ts = body["extractionTimestamp"]
        assert isinstance(root_ts, int)
        assert root_ts > 0
        metadata = body["data"][0]["metadata"]
        assert "extractionTimestamp" in metadata
        assert isinstance(metadata["extractionTimestamp"], int)
        assert metadata["extractionTimestamp"] == root_ts
        assert metadata["resourceIndex"] == 0


async def test_post_integration_raw_data_with_live_event_type(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test post_integration_raw_data_batch with event_type parameter for live events."""
    raw_data = [{"name": "test-entity"}]
    sync_id = "webhook-event-123"
    kind = "repository"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        event = make_single_entry_lakehouse_batch(
            raw_data,
            kind=kind,
            index=0,
            operation=LakehouseOperation.UPSERT,
            event_type=LakehouseEventType.LIVE_EVENT,
        )
        await lakehouse_integration_client.post_integration_raw_data_batch(
            sync_id, event
        )

        lakehouse_integration_client.client.post.assert_called_once()
        call_args = lakehouse_integration_client.client.post.call_args

        body = call_args[1]["json"]
        assert body["kind"] == kind
        assert body["eventType"] == "live-event"
        entry = body["data"][0]
        assert entry["items"] == raw_data
        assert entry["metadata"]["operation"] == "upsert"
        assert entry["metadata"]["resourceIndex"] == 0


async def test_post_integration_raw_data_with_resync_data_type(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test post_integration_raw_data_batch with event_type parameter for resync."""
    raw_data = [{"name": "test-entity"}]
    sync_id = "resync-123"
    kind = "repository"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        event = make_single_entry_lakehouse_batch(
            raw_data,
            kind=kind,
            index=0,
            operation=LakehouseOperation.UPSERT,
            event_type=LakehouseEventType.RESYNC,
        )
        await lakehouse_integration_client.post_integration_raw_data_batch(
            sync_id, event
        )

        lakehouse_integration_client.client.post.assert_called_once()
        call_args = lakehouse_integration_client.client.post.call_args

        body = call_args[1]["json"]
        assert body["kind"] == kind
        assert body["eventType"] == "resync"
        entry = body["data"][0]
        assert entry["items"] == raw_data
        assert entry["metadata"]["operation"] == "upsert"
        assert entry["metadata"]["resourceIndex"] == 0


async def test_post_integration_raw_data_without_kafka_metadata(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test post_integration_raw_data_batch without kafka_metadata parameter."""
    raw_data = [{"name": "test-entity"}]
    sync_id = "webhook-event-789"
    kind = "repository"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        event = make_single_entry_lakehouse_batch(
            raw_data,
            kind=kind,
            index=0,
            operation=LakehouseOperation.UPSERT,
        )
        await lakehouse_integration_client.post_integration_raw_data_batch(
            sync_id, event
        )

    lakehouse_integration_client.client.post.assert_called_once()
    call_args = lakehouse_integration_client.client.post.call_args

    body = call_args[1]["json"]
    assert body["kind"] == kind
    assert body["eventType"] == "live-event"
    entry = body["data"][0]
    assert entry["items"] == raw_data
    assert entry["metadata"]["operation"] == "upsert"
    assert entry["metadata"]["resourceIndex"] == 0
    assert "kafkaMetadata" not in body


async def test_post_integration_raw_data_with_event_id(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test post_integration_raw_data_batch includes eventId in body when provided."""
    raw_data = [{"name": "test-entity"}]
    sync_id = "webhook-event-abc"
    kind = "repository"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        event = make_single_entry_lakehouse_batch(
            raw_data,
            kind=kind,
            index=0,
            operation=LakehouseOperation.UPSERT,
            event_id="trace-id-xyz",
        )
        await lakehouse_integration_client.post_integration_raw_data_batch(
            sync_id, event
        )

    lakehouse_integration_client.client.post.assert_called_once()
    call_args = lakehouse_integration_client.client.post.call_args
    body = call_args[1]["json"]
    assert body["eventId"] == "trace-id-xyz"


async def test_post_integration_raw_data_without_event_id(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test post_integration_raw_data_batch omits eventId when not provided."""
    raw_data = [{"name": "test-entity"}]
    sync_id = "resync-999"
    kind = "repository"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        event = make_single_entry_lakehouse_batch(
            raw_data, kind=kind, index=0, event_id=None
        )
        await lakehouse_integration_client.post_integration_raw_data_batch(
            sync_id, event
        )

    lakehouse_integration_client.client.post.assert_called_once()
    call_args = lakehouse_integration_client.client.post.call_args
    body = call_args[1]["json"]
    assert "eventId" not in body


async def test_post_integration_raw_data_batch_single_entry(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test post_integration_raw_data_batch with a single data entry."""
    items = [{"name": "repo-one"}]
    sync_id = "sync-batch-1"
    kind = "repository"
    ts = int(datetime(2024, 1, 15, 12, 0, 0).timestamp() * 1000)

    event = make_single_entry_lakehouse_batch(
        items,
        kind=kind,
        index=0,
        operation=LakehouseOperation.UPSERT,
        event_type=LakehouseEventType.LIVE_EVENT,
        event_id="trace-123",
        extraction_timestamp=ts,
    )

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data_batch(
            sync_id, event
        )

    lakehouse_integration_client.client.post.assert_called_once()
    call_args = lakehouse_integration_client.client.post.call_args
    body = call_args[1]["json"]

    assert body["kind"] == kind
    assert body["eventType"] == "live-event"
    assert body["eventId"] == "trace-123"
    assert body["extractionTimestamp"] == ts
    assert len(body["data"]) == 1
    entry = body["data"][0]
    assert entry["items"] == items
    assert entry["request"] == {}
    assert entry["response"] == {}
    assert entry["metadata"]["operation"] == "upsert"
    assert entry["metadata"]["resourceIndex"] == 0
    assert "extractionTimestamp" in entry["metadata"]


async def test_post_integration_raw_data_batch_two_entries(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test post_integration_raw_data_batch with upsert + delete entries."""
    upsert_items = [{"name": "repo-one"}]
    delete_items = [{"id": "old-repo"}]
    sync_id = "trace-both"
    kind = "repository"
    ts = int(datetime(2024, 1, 15, 12, 0, 0).timestamp() * 1000)

    event: LakehouseDataEntryBatch = {
        "event_id": sync_id,
        "type": LakehouseEventType.LIVE_EVENT.value,
        "kind": kind,
        "event_type": LakehouseEventType.LIVE_EVENT,
        "resync_start_time": None,
        "extraction_timestamp": ts,
        "data": [
            {
                "request": {},
                "response": {},
                "items": upsert_items,
                "metadata": {
                    "operation": LakehouseOperation.UPSERT,
                    "resource_index": 0,
                    "extraction_timestamp": ts,
                },
            },
            {
                "request": {},
                "response": {},
                "items": delete_items,
                "metadata": {
                    "operation": LakehouseOperation.DELETE,
                    "resource_index": 0,
                    "extraction_timestamp": ts,
                },
            },
        ],
    }

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data_batch(
            sync_id, event
        )

    lakehouse_integration_client.client.post.assert_called_once()
    call_args = lakehouse_integration_client.client.post.call_args
    body = call_args[1]["json"]

    assert body["kind"] == kind
    assert body["eventType"] == "live-event"
    assert body["eventId"] == sync_id
    assert len(body["data"]) == 2

    upsert_entry = body["data"][0]
    assert upsert_entry["items"] == upsert_items
    assert upsert_entry["metadata"]["operation"] == "upsert"

    delete_entry = body["data"][1]
    assert delete_entry["items"] == delete_items
    assert delete_entry["metadata"]["operation"] == "delete"


async def test_post_integration_raw_data_batch_includes_environment_data(
    lakehouse_integration_client: IntegrationClientMixin,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test post_integration_raw_data_batch includes environment_data on each entry."""
    monkeypatch.setenv("FOO", "bar")
    monkeypatch.delenv("MISSING", raising=False)

    raw_data = [{"name": "repo-one"}]
    sync_id = "sync-env-vars"
    kind = "repository"

    event = make_single_entry_lakehouse_batch(
        raw_data,
        kind=kind,
        index=0,
        export_env_variables=["FOO", "MISSING"],
    )

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data_batch(
            sync_id, event
        )

    lakehouse_integration_client.client.post.assert_called_once()
    body = lakehouse_integration_client.client.post.call_args[1]["json"]

    assert body["data"][0]["environment_data"] == {"FOO": "bar", "MISSING": None}


async def test_post_integration_raw_data_batch_includes_selector_hash(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    raw_data = [{"name": "repo-one"}]
    sync_id = "sync-selector-hash"
    kind = "repository"

    event = make_single_entry_lakehouse_batch(
        raw_data,
        kind=kind,
        index=0,
        selector_hash="abc123",
    )

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data_batch(
            sync_id, event
        )

    lakehouse_integration_client.client.post.assert_called_once()
    body = lakehouse_integration_client.client.post.call_args[1]["json"]
    assert body["data"][0]["metadata"]["selectorHash"] == "abc123"


async def test_post_integration_raw_data_batch_serializes_datetime_values(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Datetime values in items/request/response are ISO-formatted in the POST body."""
    created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    raw_data = [{"id": "1", "created_at": created_at}]
    sync_id = "test-sync-123"
    kind = "file"

    event = make_single_entry_lakehouse_batch(raw_data, kind=kind, index=0)
    event["data"][0]["request"] = {"fetched_at": created_at}
    event["data"][0]["response"] = {"received_at": created_at}

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data_batch(
            sync_id, event
        )

    lakehouse_integration_client.client.post.assert_called_once()
    body = lakehouse_integration_client.client.post.call_args[1]["json"]
    entry = body["data"][0]
    assert entry["items"][0]["created_at"] == created_at.isoformat()
    assert entry["request"]["fetched_at"] == created_at.isoformat()
    assert entry["response"]["received_at"] == created_at.isoformat()


async def test_post_integration_raw_data_batch_aborts_resync_on_zero_pending_count(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    raw_data = [{"name": "repo-one"}]
    sync_id = "sync-abort"
    kind = "repository"

    response = MagicMock()
    response.status_code = 200
    response.is_error = False
    response.json.return_value = {"ok": True, "count": 0}
    lakehouse_integration_client.client.post.return_value = response

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        async with event_context(
            EventType.RESYNC,
            trigger_type="machine",
            attributes={},
        ) as current_event:
            assert not current_event.aborted
            batch_event = make_single_entry_lakehouse_batch(
                raw_data, kind=kind, index=0
            )
            await lakehouse_integration_client.post_integration_raw_data_batch(
                sync_id,
                batch_event,
            )
            assert current_event.aborted


@pytest.mark.asyncio
async def test_post_integration_raw_data_batch_retries_503() -> None:
    auth = MagicMock()
    auth.headers = AsyncMock(return_value={"Authorization": "Bearer test-token"})
    auth.integration_type = "github"
    auth.last_token_object = MagicMock()

    port_client = IntegrationClientMixin(
        integration_identifier=TEST_INTEGRATION_IDENTIFIER,
        integration_version=TEST_INTEGRATION_VERSION,
        auth=auth,
        client=MagicMock(),
    )
    port_client.get_ingest_attributes = AsyncMock(
        return_value={"ingestUrl": TEST_INGEST_URL}
    )

    http_client = OceanAsyncClient(
        transport_class=TokenRetryTransport,
        transport_kwargs={"port_client": port_client},
        retry_config=RetryConfig(max_attempts=3, base_delay=0.0),
        verify=True,
    )
    port_client.client = http_client

    inner = _inner_http_transport(http_client)
    request = httpx.Request("POST", f"{TEST_INGEST_URL}/lake/write")
    responses = [
        httpx.Response(503, request=request),
        httpx.Response(200, request=request),
    ]

    mock_handle_async_request = AsyncMock(side_effect=responses)

    with (
        patch.object(inner, "handle_async_request", mock_handle_async_request),
        patch("port_ocean.helpers.retry.asyncio.sleep", new=AsyncMock()),
    ):
        event = make_single_entry_lakehouse_batch([{"id": "1"}], kind="repo", index=0)
        await port_client.post_integration_raw_data_batch("sync-1", event)

    assert mock_handle_async_request.await_count == 2


@pytest.mark.asyncio
async def test_post_integration_raw_data_batch_retries_connect_error() -> None:
    auth = MagicMock()
    auth.headers = AsyncMock(return_value={"Authorization": "Bearer test-token"})
    auth.integration_type = "github"
    auth.last_token_object = MagicMock()

    port_client = IntegrationClientMixin(
        integration_identifier=TEST_INTEGRATION_IDENTIFIER,
        integration_version=TEST_INTEGRATION_VERSION,
        auth=auth,
        client=MagicMock(),
    )
    port_client.get_ingest_attributes = AsyncMock(
        return_value={"ingestUrl": TEST_INGEST_URL}
    )

    http_client = OceanAsyncClient(
        transport_class=TokenRetryTransport,
        transport_kwargs={"port_client": port_client},
        retry_config=RetryConfig(max_attempts=3, base_delay=0.0),
        verify=True,
    )
    port_client.client = http_client

    inner = _inner_http_transport(http_client)
    request = httpx.Request("POST", f"{TEST_INGEST_URL}/lake/write")
    responses = [
        httpx.ConnectError("connection refused", request=request),
        httpx.Response(200, request=request),
    ]

    mock_handle_async_request = AsyncMock(side_effect=responses)

    with (
        patch.object(inner, "handle_async_request", mock_handle_async_request),
        patch("port_ocean.helpers.retry.asyncio.sleep", new=AsyncMock()),
    ):
        event = make_single_entry_lakehouse_batch([{"id": "1"}], kind="repo", index=0)
        await port_client.post_integration_raw_data_batch("sync-1", event)

    assert mock_handle_async_request.await_count == 2
