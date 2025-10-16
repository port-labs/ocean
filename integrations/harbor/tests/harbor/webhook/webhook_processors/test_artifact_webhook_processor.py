"""Tests for Harbor artifact webhook processor."""

import pytest
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

from harbor.webhook.webhook_processors.artifact_webhook_processor import (
    ArtifactWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.handlers.port_app_config.models import ResourceConfig


class TestArtifactWebhookProcessor:
    """Test ArtifactWebhookProcessor."""

    @pytest.fixture
    def mock_webhook_event(self) -> WebhookEvent:
        """Create mock webhook event."""
        return WebhookEvent(payload={}, headers={}, trace_id="test-trace-id")

    @pytest.fixture
    def processor(self, mock_webhook_event: WebhookEvent) -> ArtifactWebhookProcessor:
        """Create processor instance."""
        with patch(
            "harbor.webhook.webhook_processors.artifact_webhook_processor.init_client"
        ):
            return ArtifactWebhookProcessor(mock_webhook_event)

    @pytest.fixture
    def mock_payload(self) -> Dict[str, Any]:
        """Mock webhook payload."""
        return {
            "type": "PUSH_ARTIFACT",
            "event_data": {
                "repository": {
                    "name": "test/repo",
                    "project_id": 1,
                    "repository_id": 1,
                    "namespace": "test",
                    "repo_full_name": "test/repo",
                },
                "resources": [{"digest": "sha256:abc123", "tag": "latest"}],
            },
        }

    @pytest.fixture
    def mock_resource_config(self) -> ResourceConfig:
        """Mock resource config."""
        return MagicMock(spec=ResourceConfig)

    @pytest.mark.asyncio
    async def test_validate_payload_valid_event(
        self, processor: ArtifactWebhookProcessor, mock_payload: Dict[str, Any]
    ) -> None:
        """Test payload validation with valid event."""
        result = await processor.validate_payload(mock_payload)
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_payload_invalid_event(
        self, processor: ArtifactWebhookProcessor
    ) -> None:
        """Test payload validation with invalid event."""
        payload: Dict[str, Any] = {"type": "INVALID_EVENT"}
        result = await processor.validate_payload(payload)
        assert result is False

    @pytest.mark.asyncio
    async def test_handle_event_push_artifact(
        self, processor: ArtifactWebhookProcessor, mock_payload: Dict[str, Any], mock_resource_config: ResourceConfig
    ) -> None:
        """Test handling PUSH_ARTIFACT event."""
        with (
            patch(
                "harbor.webhook.webhook_processors.artifact_webhook_processor.init_client"
            ) as mock_init_client,
            patch(
                "harbor.webhook.webhook_processors.artifact_webhook_processor.HarborArtifactExporter"
            ) as mock_exporter_class,
        ):

            mock_client = AsyncMock()
            mock_init_client.return_value = mock_client

            mock_exporter = AsyncMock()
            mock_exporter_class.return_value = mock_exporter
            mock_exporter.get_resource.return_value = {
                "id": "test-artifact",
                "name": "test/repo:latest",
            }

            result = await processor.handle_event(mock_payload, mock_resource_config)

            assert len(result.updated_raw_results) == 1
            assert len(result.deleted_raw_results) == 0

    @pytest.mark.asyncio
    async def test_handle_event_delete_artifact(
        self, processor: ArtifactWebhookProcessor, mock_resource_config: ResourceConfig
    ) -> None:
        """Test handling DELETE_ARTIFACT event."""
        payload: Dict[str, Any] = {
            "type": "DELETE_ARTIFACT",
            "event_data": {
                "repository": {
                    "name": "test/repo",
                    "project_id": 1,
                    "repository_id": 1,
                    "namespace": "test",
                    "repo_full_name": "test/repo",
                },
                "resources": [{"digest": "sha256:abc123", "tag": "latest"}],
            },
        }

        result = await processor.handle_event(payload, mock_resource_config)

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0]["tag"] == "latest"
