from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from harbor.helpers.utils import ObjectKind
from harbor.webhooks.events import HarborEventType
from harbor.webhooks.processors.project_webhook_processor import ProjectWebhookProcessor


@pytest.fixture
def processor():
    return ProjectWebhookProcessor()


@pytest.fixture
def mock_client():
    return AsyncMock()


@pytest.fixture
def mock_exporter():
    return AsyncMock()


class TestProjectWebhookProcessorShouldProcessEvent:
    @pytest.mark.asyncio
    async def test_returns_true_for_quota_exceed_event(self, processor):
        event = WebhookEvent(payload={"type": HarborEventType.QUOTA_EXCEED}, headers={})

        assert await processor.should_process_event(event) is True

    @pytest.mark.asyncio
    async def test_returns_true_for_quota_warning_event(self, processor):
        event = WebhookEvent(payload={"type": HarborEventType.QUOTA_WARNING}, headers={})

        assert await processor.should_process_event(event) is True

    @pytest.mark.asyncio
    async def test_returns_false_for_push_artifact_event(self, processor):
        event = WebhookEvent(payload={"type": HarborEventType.PUSH_ARTIFACT}, headers={})

        assert await processor.should_process_event(event) is False


class TestProjectWebhookProcessorGetMatchingKinds:
    @pytest.mark.asyncio
    async def test_returns_project_kind(self, processor):
        event = WebhookEvent(payload={}, headers={})

        kinds = await processor.get_matching_kinds(event)

        assert kinds == [ObjectKind.PROJECT]


class TestProjectWebhookProcessorValidatePayload:
    @pytest.mark.asyncio
    async def test_returns_true_when_required_fields_present(self, processor):
        payload = {"type": "QUOTA_EXCEED", "event_data": {}}

        assert await processor.validate_payload(payload) is True

    @pytest.mark.asyncio
    async def test_returns_false_when_type_missing(self, processor):
        payload = {"event_data": {}}

        assert await processor.validate_payload(payload) is False

    @pytest.mark.asyncio
    async def test_returns_false_when_event_data_missing(self, processor):
        payload = {"type": "QUOTA_EXCEED"}

        assert await processor.validate_payload(payload) is False


class TestProjectWebhookProcessorHandleEvent:
    @pytest.mark.asyncio
    async def test_quota_exceed_fetches_and_returns_updated_project(self, processor, mock_client, mock_exporter):
        payload = {"type": HarborEventType.QUOTA_EXCEED, "event_data": {"repository": {"namespace": "opensource"}}}

        mock_project = {"name": "opensource", "project_id": 1}
        mock_exporter.get_resource.return_value = mock_project

        with patch("harbor.webhooks.processors.project_webhook_processor.HarborClientFactory") as mock_factory:
            mock_factory.get_client.return_value = mock_client

            with patch("harbor.webhooks.processors.project_webhook_processor.HarborProjectExporter") as MockExporter:
                MockExporter.return_value = mock_exporter

                result = await processor.handle_event(payload, MagicMock())

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == mock_project
        assert len(result.deleted_raw_results) == 0

        mock_exporter.get_resource.assert_called_once_with("opensource")

    @pytest.mark.asyncio
    async def test_quota_warning_fetches_and_returns_updated_project(self, processor, mock_client, mock_exporter):
        payload = {"type": HarborEventType.QUOTA_WARNING, "event_data": {"repository": {"namespace": "production"}}}

        mock_project = {"name": "production", "project_id": 2}
        mock_exporter.get_resource.return_value = mock_project

        with patch("harbor.webhooks.processors.project_webhook_processor.HarborClientFactory") as mock_factory:
            mock_factory.get_client.return_value = mock_client

            with patch("harbor.webhooks.processors.project_webhook_processor.HarborProjectExporter") as MockExporter:
                MockExporter.return_value = mock_exporter

                result = await processor.handle_event(payload, MagicMock())

        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0

    @pytest.mark.asyncio
    async def test_extracts_project_name_from_repository_name_when_namespace_missing(
        self, processor, mock_client, mock_exporter
    ):
        payload = {"type": HarborEventType.QUOTA_EXCEED, "event_data": {"repository": {"name": "opensource/nginx"}}}

        mock_project = {"name": "opensource"}
        mock_exporter.get_resource.return_value = mock_project

        with patch("harbor.webhooks.processors.project_webhook_processor.HarborClientFactory") as mock_factory:
            mock_factory.get_client.return_value = mock_client

            with patch("harbor.webhooks.processors.project_webhook_processor.HarborProjectExporter") as MockExporter:
                MockExporter.return_value = mock_exporter

                result = await processor.handle_event(payload, MagicMock())

        mock_exporter.get_resource.assert_called_once_with("opensource")

    @pytest.mark.asyncio
    async def test_returns_empty_results_when_project_name_cannot_be_extracted(self, processor, mock_client):
        payload = {"type": HarborEventType.QUOTA_EXCEED, "event_data": {"repository": {}}}

        with patch("harbor.webhooks.processors.project_webhook_processor.HarborClientFactory") as mock_factory:
            mock_factory.get_client.return_value = mock_client

            result = await processor.handle_event(payload, MagicMock())

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0

    @pytest.mark.asyncio
    async def test_handles_fetch_failure_gracefully(self, processor, mock_client, mock_exporter):
        payload = {"type": HarborEventType.QUOTA_EXCEED, "event_data": {"repository": {"namespace": "opensource"}}}

        mock_exporter.get_resource.side_effect = Exception("API Error")

        with patch("harbor.webhooks.processors.project_webhook_processor.HarborClientFactory") as mock_factory:
            mock_factory.get_client.return_value = mock_client

            with patch("harbor.webhooks.processors.project_webhook_processor.HarborProjectExporter") as MockExporter:
                MockExporter.return_value = mock_exporter

                result = await processor.handle_event(payload, MagicMock())

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0
