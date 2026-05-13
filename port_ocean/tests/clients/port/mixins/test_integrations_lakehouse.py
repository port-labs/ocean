from typing import Any
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from port_ocean.clients.port.mixins.integrations import IntegrationClientMixin
from port_ocean.core.models import LakehouseOperation, LakehouseEventType


TEST_INTEGRATION_IDENTIFIER = "test-integration"
TEST_INTEGRATION_VERSION = "1.0.0"
TEST_INGEST_URL = "https://api.example.com"


@pytest.fixture
def lakehouse_integration_client(monkeypatch: Any) -> IntegrationClientMixin:
    """Create an IntegrationClientMixin instance for lakehouse testing."""
    auth = MagicMock()
    auth.headers = AsyncMock()
    auth.headers.return_value = {"Authorization": "Bearer test-token"}
    auth.ingest_url = TEST_INGEST_URL
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

    return integration_client


async def test_post_integration_raw_data_default_operation(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test post_integration_raw_data with default UPSERT operation."""
    raw_data = [{"name": "repo-one", "stars": 100}, {"name": "repo-two", "stars": 200}]
    sync_id = "test-sync-123"
    kind = "repository"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data(
            raw_data, sync_id, kind, index=0
        )

        lakehouse_integration_client.client.post.assert_called_once()
        call_args = lakehouse_integration_client.client.post.call_args

        expected_url = f"{TEST_INGEST_URL}/lake/write/integration-type/github/integration/{TEST_INTEGRATION_IDENTIFIER}/sync/{sync_id}/kind/{kind}"
        assert call_args[0][0] == expected_url

        body = call_args[1]["json"]
        assert body["kind"] == kind
        assert body["eventType"] == "live-event"
        assert len(body["data"]) == 1
        entry = body["data"][0]
        assert entry["items"] == raw_data
        assert entry["request"] == {}
        assert entry["response"] == {}
        assert entry["metadata"]["operation"] == "upsert"
        assert entry["metadata"]["resourceIndex"] == 0
        assert "extractionTimestamp" in entry["metadata"]
        assert "resyncStartTime" not in body
        assert "eventId" not in body


async def test_post_integration_raw_data_with_upsert_operation(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test post_integration_raw_data with explicit UPSERT operation."""
    raw_data = [{"id": "123", "name": "test"}]
    sync_id = "webhook-event-456"
    kind = "service"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data(
            raw_data, sync_id, kind, index=0, operation=LakehouseOperation.UPSERT
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
    """Test post_integration_raw_data with DELETE operation."""
    raw_data = [{"id": "789"}]
    sync_id = "webhook-event-789"
    kind = "repository"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data(
            raw_data, sync_id, kind, index=0, operation=LakehouseOperation.DELETE
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
    """Test that post_integration_raw_data constructs the correct URL."""
    raw_data = [{"test": "data"}]
    sync_id = "sync-abc-123"
    kind = "deployment"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data(
            raw_data, sync_id, kind, index=2, operation=LakehouseOperation.UPSERT
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
    """Test post_integration_raw_data with empty raw data list."""
    raw_data: list = []
    sync_id = "sync-empty"
    kind = "repository"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data(
            raw_data, sync_id, kind, index=0, operation=LakehouseOperation.DELETE
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
    """Test that post_integration_raw_data includes extractionTimestamp."""
    raw_data = [{"name": "test"}]
    sync_id = "sync-timestamp-test"
    kind = "service"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data(
            raw_data, sync_id, kind, index=0
        )

        lakehouse_integration_client.client.post.assert_called_once()
        call_args = lakehouse_integration_client.client.post.call_args

        metadata = call_args[1]["json"]["data"][0]["metadata"]
        assert "extractionTimestamp" in metadata
        assert isinstance(metadata["extractionTimestamp"], int)
        assert metadata["extractionTimestamp"] > 0
        assert metadata["resourceIndex"] == 0


async def test_post_integration_raw_data_with_live_event_type(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test post_integration_raw_data with event_type parameter for live events."""
    raw_data = [{"name": "test-entity"}]
    sync_id = "webhook-event-123"
    kind = "repository"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data(
            raw_data,
            sync_id,
            kind,
            index=0,
            operation=LakehouseOperation.UPSERT,
            event_type=LakehouseEventType.LIVE_EVENT,
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
    """Test post_integration_raw_data with event_type parameter for resync."""
    raw_data = [{"name": "test-entity"}]
    sync_id = "resync-123"
    kind = "repository"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data(
            raw_data,
            sync_id,
            kind,
            index=0,
            operation=LakehouseOperation.UPSERT,
            event_type=LakehouseEventType.RESYNC,
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
    """Test post_integration_raw_data without kafka_metadata parameter."""
    raw_data = [{"name": "test-entity"}]
    sync_id = "webhook-event-789"
    kind = "repository"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data(
            raw_data,
            sync_id,
            kind,
            index=0,
            operation=LakehouseOperation.UPSERT,
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
    """Test post_integration_raw_data includes eventId in body when provided."""
    raw_data = [{"name": "test-entity"}]
    sync_id = "webhook-event-abc"
    kind = "repository"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data(
            raw_data,
            sync_id,
            kind,
            index=0,
            operation=LakehouseOperation.UPSERT,
            event_id="trace-id-xyz",
        )

    lakehouse_integration_client.client.post.assert_called_once()
    call_args = lakehouse_integration_client.client.post.call_args
    body = call_args[1]["json"]
    assert body["eventId"] == "trace-id-xyz"


async def test_post_integration_raw_data_without_event_id(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test post_integration_raw_data omits eventId when not provided."""
    raw_data = [{"name": "test-entity"}]
    sync_id = "resync-999"
    kind = "repository"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data(
            raw_data,
            sync_id,
            kind,
            index=0,
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

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data_batch(
            [{"operation": LakehouseOperation.UPSERT, "items": items, "index": 0}],
            sync_id,
            kind,
            event_type=LakehouseEventType.LIVE_EVENT,
            event_id="trace-123",
        )

    lakehouse_integration_client.client.post.assert_called_once()
    call_args = lakehouse_integration_client.client.post.call_args
    body = call_args[1]["json"]

    assert body["kind"] == kind
    assert body["eventType"] == "live-event"
    assert body["eventId"] == "trace-123"
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

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data_batch(
            [
                {
                    "operation": LakehouseOperation.UPSERT,
                    "items": upsert_items,
                    "index": 0,
                },
                {
                    "operation": LakehouseOperation.DELETE,
                    "items": delete_items,
                    "index": 0,
                },
            ],
            sync_id,
            kind,
            event_type=LakehouseEventType.LIVE_EVENT,
            event_id=sync_id,
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
