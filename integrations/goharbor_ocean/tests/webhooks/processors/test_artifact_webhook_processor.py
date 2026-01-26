from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from harbor.helpers.utils import ObjectKind
from harbor.webhooks.events import HarborEventType
from harbor.webhooks.processors.artifact_webhook_processor import (
    ArtifactWebhookProcessor,
)


@pytest.fixture
def processor():
    return ArtifactWebhookProcessor()


@pytest.fixture
def mock_client():
    return AsyncMock()


@pytest.fixture
def mock_exporter():
    return AsyncMock()


class TestArtifactWebhookProcessorShouldProcessEvent:
    @pytest.mark.asyncio
    async def test_returns_true_for_push_artifact_event(self, processor):
        event = WebhookEvent(payload={"type": HarborEventType.PUSH_ARTIFACT}, headers={})

        assert await processor.should_process_event(event) is True

    @pytest.mark.asyncio
    async def test_returns_true_for_delete_artifact_event(self, processor):
        event = WebhookEvent(payload={"type": HarborEventType.DELETE_ARTIFACT}, headers={})

        assert await processor.should_process_event(event) is True

    @pytest.mark.asyncio
    async def test_returns_true_for_scanning_completed_event(self, processor):
        event = WebhookEvent(payload={"type": HarborEventType.SCANNING_COMPLETED}, headers={})

        assert await processor.should_process_event(event) is True

    @pytest.mark.asyncio
    async def test_returns_false_for_quota_event(self, processor):
        event = WebhookEvent(payload={"type": HarborEventType.QUOTA_EXCEED}, headers={})

        assert await processor.should_process_event(event) is False


class TestArtifactWebhookProcessorGetMatchingKinds:
    @pytest.mark.asyncio
    async def test_returns_artifact_kind(self, processor):
        event = WebhookEvent(payload={}, headers={})

        kinds = await processor.get_matching_kinds(event)

        assert kinds == [ObjectKind.ARTIFACT]


class TestArtifactWebhookProcessorValidatePayload:
    @pytest.mark.asyncio
    async def test_returns_true_when_required_fields_present(self, processor):
        payload = {"type": "PUSH_ARTIFACT", "event_data": {}}

        assert await processor.validate_payload(payload) is True

    @pytest.mark.asyncio
    async def test_returns_false_when_type_missing(self, processor):
        payload = {"event_data": {}}

        assert await processor.validate_payload(payload) is False

    @pytest.mark.asyncio
    async def test_returns_false_when_event_data_missing(self, processor):
        payload = {"type": "PUSH_ARTIFACT"}

        assert await processor.validate_payload(payload) is False


class TestArtifactWebhookProcessorHandleEvent:
    @pytest.mark.asyncio
    async def test_push_artifact_fetches_and_returns_updated_artifact(self, processor, mock_client, mock_exporter):
        payload = {
            "type": HarborEventType.PUSH_ARTIFACT,
            "event_data": {
                "repository": {"namespace": "opensource", "name": "nginx"},
                "resources": [{"digest": "sha256:abc123"}],
            },
        }

        mock_artifact = {"digest": "sha256:abc123", "project_id": 1}
        mock_exporter.get_resource.return_value = mock_artifact

        with patch("harbor.webhooks.processors.artifact_webhook_processor.HarborClientFactory") as mock_factory:
            mock_factory.get_client.return_value = mock_client

            with patch("harbor.webhooks.processors.artifact_webhook_processor.HarborArtifactExporter") as MockExporter:
                MockExporter.return_value = mock_exporter

                result = await processor.handle_event(payload, MagicMock())

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == mock_artifact
        assert len(result.deleted_raw_results) == 0

        mock_exporter.get_resource.assert_called_once_with(
            project_name="opensource", repository_name="nginx", reference="sha256:abc123"
        )

    @pytest.mark.asyncio
    async def test_scanning_completed_fetches_and_returns_updated_artifact(self, processor, mock_client, mock_exporter):
        payload = {
            "type": HarborEventType.SCANNING_COMPLETED,
            "event_data": {
                "repository": {"namespace": "production", "name": "redis"},
                "resources": [{"digest": "sha256:def456", "scan_overview": {}}],
            },
        }

        mock_artifact = {"digest": "sha256:def456", "scan_overview": {"severity": "High"}}
        mock_exporter.get_resource.return_value = mock_artifact

        with patch("harbor.webhooks.processors.artifact_webhook_processor.HarborClientFactory") as mock_factory:
            mock_factory.get_client.return_value = mock_client

            with patch("harbor.webhooks.processors.artifact_webhook_processor.HarborArtifactExporter") as MockExporter:
                MockExporter.return_value = mock_exporter

                result = await processor.handle_event(payload, MagicMock())

        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0

    @pytest.mark.asyncio
    async def test_delete_artifact_returns_deleted_artifacts(self, processor, mock_client):
        payload = {
            "type": HarborEventType.DELETE_ARTIFACT,
            "event_data": {
                "repository": {"namespace": "staging", "name": "postgres"},
                "resources": [{"digest": "sha256:xyz789"}, {"digest": "sha256:uvw456"}],
            },
        }

        with patch("harbor.webhooks.processors.artifact_webhook_processor.HarborClientFactory") as mock_factory:
            mock_factory.get_client.return_value = mock_client

            with patch("harbor.webhooks.processors.artifact_webhook_processor.HarborArtifactExporter"):
                result = await processor.handle_event(payload, MagicMock())

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 2
        assert result.deleted_raw_results[0]["digest"] == "sha256:xyz789"
        assert result.deleted_raw_results[0]["__project"] == "staging"
        assert result.deleted_raw_results[0]["__repository"] == "postgres"

    @pytest.mark.asyncio
    async def test_returns_empty_results_when_project_name_missing(self, processor, mock_client):
        payload = {
            "type": HarborEventType.PUSH_ARTIFACT,
            "event_data": {"repository": {"name": "nginx"}, "resources": [{"digest": "sha256:abc"}]},
        }

        with patch("harbor.webhooks.processors.artifact_webhook_processor.HarborClientFactory") as mock_factory:
            mock_factory.get_client.return_value = mock_client

            result = await processor.handle_event(payload, MagicMock())

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0

    @pytest.mark.asyncio
    async def test_returns_empty_results_when_repository_name_missing(self, processor, mock_client):
        payload = {
            "type": HarborEventType.PUSH_ARTIFACT,
            "event_data": {"repository": {"namespace": "opensource"}, "resources": [{"digest": "sha256:abc"}]},
        }

        with patch("harbor.webhooks.processors.artifact_webhook_processor.HarborClientFactory") as mock_factory:
            mock_factory.get_client.return_value = mock_client

            result = await processor.handle_event(payload, MagicMock())

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0

    @pytest.mark.asyncio
    async def test_handles_fetch_failure_gracefully(self, processor, mock_client, mock_exporter):
        payload = {
            "type": HarborEventType.PUSH_ARTIFACT,
            "event_data": {
                "repository": {"namespace": "opensource", "name": "nginx"},
                "resources": [{"digest": "sha256:abc123"}],
            },
        }

        mock_exporter.get_resource.side_effect = Exception("API Error")

        with patch("harbor.webhooks.processors.artifact_webhook_processor.HarborClientFactory") as mock_factory:
            mock_factory.get_client.return_value = mock_client

            with patch("harbor.webhooks.processors.artifact_webhook_processor.HarborArtifactExporter") as MockExporter:
                MockExporter.return_value = mock_exporter

                result = await processor.handle_event(payload, MagicMock())

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0

    @pytest.mark.asyncio
    async def test_processes_multiple_resources(self, processor, mock_client, mock_exporter):
        payload = {
            "type": HarborEventType.PUSH_ARTIFACT,
            "event_data": {
                "repository": {"namespace": "opensource", "name": "nginx"},
                "resources": [{"digest": "sha256:abc123"}, {"digest": "sha256:def456"}],
            },
        }

        mock_exporter.get_resource.side_effect = [{"digest": "sha256:abc123"}, {"digest": "sha256:def456"}]

        with patch("harbor.webhooks.processors.artifact_webhook_processor.HarborClientFactory") as mock_factory:
            mock_factory.get_client.return_value = mock_client

            with patch("harbor.webhooks.processors.artifact_webhook_processor.HarborArtifactExporter") as MockExporter:
                MockExporter.return_value = mock_exporter

                result = await processor.handle_event(payload, MagicMock())

        assert len(result.updated_raw_results) == 2
        assert mock_exporter.get_resource.call_count == 2
