from typing import Any
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from port_ocean.clients.port.mixins.integrations import IntegrationClientMixin
from port_ocean.core.models import LakehouseOperation


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
            raw_data, sync_id, kind
        )

        lakehouse_integration_client.client.post.assert_called_once()
        call_args = lakehouse_integration_client.client.post.call_args

        expected_url = f"{TEST_INGEST_URL}/lake/write/integration-type/github/integration/{TEST_INTEGRATION_IDENTIFIER}/sync/{sync_id}/kind/{kind}"
        assert call_args[0][0] == expected_url

        expected_json = call_args[1]["json"]
        assert expected_json["items"] == raw_data
        assert expected_json["operation"] == "upsert"
        assert "extractionTimestamp" in expected_json


async def test_post_integration_raw_data_with_upsert_operation(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test post_integration_raw_data with explicit UPSERT operation."""
    raw_data = [{"id": "123", "name": "test"}]
    sync_id = "webhook-event-456"
    kind = "service"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data(
            raw_data, sync_id, kind, operation=LakehouseOperation.UPSERT
        )

        lakehouse_integration_client.client.post.assert_called_once()
        call_args = lakehouse_integration_client.client.post.call_args

        expected_json = call_args[1]["json"]
        assert expected_json["items"] == raw_data
        assert expected_json["operation"] == "upsert"


async def test_post_integration_raw_data_with_delete_operation(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test post_integration_raw_data with DELETE operation."""
    raw_data = [{"id": "789"}]
    sync_id = "webhook-event-789"
    kind = "repository"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data(
            raw_data, sync_id, kind, operation=LakehouseOperation.DELETE
        )

        lakehouse_integration_client.client.post.assert_called_once()
        call_args = lakehouse_integration_client.client.post.call_args

        expected_json = call_args[1]["json"]
        assert expected_json["items"] == raw_data
        assert expected_json["operation"] == "delete"


async def test_post_integration_raw_data_url_construction(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test that post_integration_raw_data constructs the correct URL."""
    raw_data = [{"test": "data"}]
    sync_id = "sync-abc-123"
    kind = "deployment"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data(
            raw_data, sync_id, kind, operation=LakehouseOperation.UPSERT
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


async def test_post_integration_raw_data_empty_list(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test post_integration_raw_data with empty raw data list."""
    raw_data: list = []
    sync_id = "sync-empty"
    kind = "repository"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data(
            raw_data, sync_id, kind, operation=LakehouseOperation.DELETE
        )

        lakehouse_integration_client.client.post.assert_called_once()
        call_args = lakehouse_integration_client.client.post.call_args

        expected_json = call_args[1]["json"]
        assert expected_json["items"] == []
        assert expected_json["operation"] == "delete"


async def test_post_integration_raw_data_extraction_timestamp(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test that post_integration_raw_data includes extractionTimestamp."""
    raw_data = [{"name": "test"}]
    sync_id = "sync-timestamp-test"
    kind = "service"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data(
            raw_data, sync_id, kind
        )

        lakehouse_integration_client.client.post.assert_called_once()
        call_args = lakehouse_integration_client.client.post.call_args

        expected_json = call_args[1]["json"]
        assert "extractionTimestamp" in expected_json
        assert isinstance(expected_json["extractionTimestamp"], int)
        assert expected_json["extractionTimestamp"] > 0


async def test_post_integration_raw_data_with_data_type(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test post_integration_raw_data with data_type parameter for live events."""
    raw_data = [{"name": "test-entity"}]
    sync_id = "webhook-event-123"
    kind = "repository"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data(
            raw_data,
            sync_id,
            kind,
            operation=LakehouseOperation.UPSERT,
            data_type="live-event",
        )

        lakehouse_integration_client.client.post.assert_called_once()
        call_args = lakehouse_integration_client.client.post.call_args

        expected_json = call_args[1]["json"]
        assert expected_json["items"] == raw_data
        assert expected_json["operation"] == "upsert"
        assert expected_json["type"] == "live-event"


async def test_post_integration_raw_data_with_resync_data_type(
    lakehouse_integration_client: IntegrationClientMixin,
) -> None:
    """Test post_integration_raw_data with data_type parameter for resync."""
    raw_data = [{"name": "test-entity"}]
    sync_id = "resync-123"
    kind = "repository"

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await lakehouse_integration_client.post_integration_raw_data(
            raw_data,
            sync_id,
            kind,
            operation=LakehouseOperation.UPSERT,
            data_type="resync",
        )

        lakehouse_integration_client.client.post.assert_called_once()
        call_args = lakehouse_integration_client.client.post.call_args

        expected_json = call_args[1]["json"]
        assert expected_json["items"] == raw_data
        assert expected_json["operation"] == "upsert"
        assert expected_json["type"] == "resync"
