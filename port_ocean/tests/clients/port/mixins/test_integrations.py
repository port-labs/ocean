from typing import Any
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
import httpx

from port_ocean.clients.port.mixins.integrations import IntegrationClientMixin


TEST_INTEGRATION_IDENTIFIER = "test-integration"
TEST_INTEGRATION_VERSION = "1.0.0"
TEST_INGEST_URL = "https://api.example.com"

BASIC_KIND_METRICS = {
    "eventId": "event-123",
    "kindIdentifier": "service",
    "metrics": {"count": 5},
}

KIND_METRICS_WITH_SLASH = {
    "eventId": "event-456",
    "kindIdentifier": "kind/kind1",
    "metrics": {"count": 10},
}

EVENT_METRICS_WITH_SLASH = {
    "eventId": "event/123",
    "kindIdentifier": "service",
    "metrics": {"count": 15},
}

BOTH_METRICS_WITH_SLASH = {
    "eventId": "namespace/event/123",
    "kindIdentifier": "app/service/v1",
    "metrics": {"count": 20},
}

COMPLEX_KIND_METRICS = {
    "eventId": "complete/test/123",
    "kindIdentifier": "complex/kind/identifier",
    "syncStart": "2024-01-01T00:00:00Z",
    "syncEnd": "2024-01-01T01:00:00Z",
    "metrics": {"totalEntities": 100, "successfulEntities": 95, "failedEntities": 5},
}


@pytest.fixture
def integration_client(monkeypatch: Any) -> IntegrationClientMixin:
    """Create an IntegrationClientMixin instance with mocked dependencies."""
    auth = MagicMock()
    auth.headers = AsyncMock()
    auth.headers.return_value = {"Authorization": "Bearer test-token"}

    client = MagicMock()
    client.put = AsyncMock()
    client.put.return_value = MagicMock()
    client.put.return_value.status_code = 200
    client.put.return_value.is_error = False

    integration_client = IntegrationClientMixin(
        integration_identifier=TEST_INTEGRATION_IDENTIFIER,
        integration_version=TEST_INTEGRATION_VERSION,
        auth=auth,
        client=client,
    )

    mock_get_metrics_attributes = AsyncMock()
    mock_get_metrics_attributes.return_value = {"ingestUrl": TEST_INGEST_URL}
    monkeypatch.setattr(
        integration_client, "get_metrics_attributes", mock_get_metrics_attributes
    )

    return integration_client


async def test_put_integration_sync_metrics_basic(
    integration_client: IntegrationClientMixin,
) -> None:
    """Test basic functionality of put_integration_sync_metrics."""
    with patch(
        "port_ocean.clients.port.mixins.integrations.handle_port_status_code"
    ) as mock_handle:
        await integration_client.put_integration_sync_metrics(BASIC_KIND_METRICS)

        integration_client.get_metrics_attributes.assert_called_once()

        integration_client.auth.headers.assert_called_once()

        integration_client.client.put.assert_called_once()
        call_args = integration_client.client.put.call_args

        expected_url = f"{TEST_INGEST_URL}/syncMetrics/resync/event-123/kind/service"
        assert call_args[0][0] == expected_url

        expected_headers = {"Authorization": "Bearer test-token"}
        assert call_args[1]["headers"] == expected_headers

        expected_json = {"syncKindMetrics": BASIC_KIND_METRICS}
        assert call_args[1]["json"] == expected_json

        mock_handle.assert_called_once_with(
            integration_client.client.put.return_value, should_log=False
        )


async def test_put_integration_sync_metrics_with_slash_in_kind_identifier(
    integration_client: IntegrationClientMixin,
) -> None:
    """Test put_integration_sync_metrics with forward slash in kindIdentifier."""
    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await integration_client.put_integration_sync_metrics(KIND_METRICS_WITH_SLASH)

        integration_client.client.put.assert_called_once()
        call_args = integration_client.client.put.call_args

        expected_url = (
            f"{TEST_INGEST_URL}/syncMetrics/resync/event-456/kind/kind%2Fkind1"
        )
        assert call_args[0][0] == expected_url

        expected_json = {"syncKindMetrics": KIND_METRICS_WITH_SLASH}
        assert call_args[1]["json"] == expected_json


async def test_put_integration_sync_metrics_with_slash_in_event_id(
    integration_client: IntegrationClientMixin,
) -> None:
    """Test put_integration_sync_metrics with forward slash in eventId."""
    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await integration_client.put_integration_sync_metrics(EVENT_METRICS_WITH_SLASH)

        integration_client.client.put.assert_called_once()
        call_args = integration_client.client.put.call_args

        expected_url = f"{TEST_INGEST_URL}/syncMetrics/resync/event%2F123/kind/service"
        assert call_args[0][0] == expected_url


async def test_put_integration_sync_metrics_with_slashes_in_both_fields(
    integration_client: IntegrationClientMixin,
) -> None:
    """Test put_integration_sync_metrics with forward slashes in both eventId and kindIdentifier."""
    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await integration_client.put_integration_sync_metrics(BOTH_METRICS_WITH_SLASH)

        integration_client.client.put.assert_called_once()
        call_args = integration_client.client.put.call_args

        expected_url = f"{TEST_INGEST_URL}/syncMetrics/resync/namespace%2Fevent%2F123/kind/app%2Fservice%2Fv1"
        assert call_args[0][0] == expected_url


async def test_put_integration_sync_metrics_with_special_characters(
    integration_client: IntegrationClientMixin,
) -> None:
    """Test put_integration_sync_metrics with various special characters that need URL encoding."""
    special_metrics = {
        "eventId": "event@123#test",
        "kindIdentifier": "kind with spaces+symbols",
        "metrics": {"count": 25},
    }

    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await integration_client.put_integration_sync_metrics(special_metrics)

        integration_client.client.put.assert_called_once()
        call_args = integration_client.client.put.call_args

        expected_url = f"{TEST_INGEST_URL}/syncMetrics/resync/event%40123%23test/kind/kind+with+spaces%2Bsymbols"
        assert call_args[0][0] == expected_url


async def test_put_integration_sync_metrics_complete_flow(
    integration_client: IntegrationClientMixin,
) -> None:
    """Test the complete flow of put_integration_sync_metrics method."""
    with patch("port_ocean.clients.port.mixins.integrations.handle_port_status_code"):
        await integration_client.put_integration_sync_metrics(COMPLEX_KIND_METRICS)

        integration_client.get_metrics_attributes.assert_called_once()
        integration_client.auth.headers.assert_called_once()
        integration_client.client.put.assert_called_once()

        call_args = integration_client.client.put.call_args
        assert "complete%2Ftest%2F123" in call_args[0][0]
        assert "complex%2Fkind%2Fidentifier" in call_args[0][0]

        assert call_args[1]["json"]["syncKindMetrics"] == COMPLEX_KIND_METRICS


async def test_put_integration_sync_metrics_error_handling(
    integration_client: IntegrationClientMixin,
    monkeypatch: Any,
) -> None:
    """Test that put_integration_sync_metrics properly handles errors."""
    mock_get_metrics_attributes = AsyncMock()
    mock_get_metrics_attributes.side_effect = httpx.HTTPStatusError(
        message="Test error", request=MagicMock(), response=MagicMock()
    )
    monkeypatch.setattr(
        integration_client, "get_metrics_attributes", mock_get_metrics_attributes
    )

    with pytest.raises(httpx.HTTPStatusError):
        await integration_client.put_integration_sync_metrics(BASIC_KIND_METRICS)
