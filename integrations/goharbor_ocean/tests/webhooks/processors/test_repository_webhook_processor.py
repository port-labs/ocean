from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from harbor.helpers.utils import ObjectKind
from harbor.webhooks.events import HarborEventType
from harbor.webhooks.processors.repository_webhook_processor import (
    RepositoryWebhookProcessor,
)


@pytest.fixture
def processor():
    return RepositoryWebhookProcessor()


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get_repository = AsyncMock()
    return client


@pytest.fixture
def mock_exporter():
    return AsyncMock()


class TestRepositoryWebhookProcessorShouldProcessEvent:
    @pytest.mark.asyncio
    async def test_returns_true_for_push_artifact_event(self, processor):
        event = WebhookEvent(payload={"type": HarborEventType.PUSH_ARTIFACT}, headers={})

        assert await processor.should_process_event(event) is True

    @pytest.mark.asyncio
    async def test_returns_true_for_delete_artifact_event(self, processor):
        event = WebhookEvent(payload={"type": HarborEventType.DELETE_ARTIFACT}, headers={})

        assert await processor.should_process_event(event) is True

    @pytest.mark.asyncio
    async def test_returns_true_for_replication_event(self, processor):
        event = WebhookEvent(payload={"type": HarborEventType.REPLICATION}, headers={})

        assert await processor.should_process_event(event) is True

    @pytest.mark.asyncio
    async def test_returns_false_for_quota_event(self, processor):
        event = WebhookEvent(payload={"type": HarborEventType.QUOTA_EXCEED}, headers={})

        assert await processor.should_process_event(event) is False


class TestRepositoryWebhookProcessorGetMatchingKinds:
    @pytest.mark.asyncio
    async def test_returns_repository_kind(self, processor):
        event = WebhookEvent(payload={}, headers={})

        kinds = await processor.get_matching_kinds(event)

        assert kinds == [ObjectKind.REPOSITORY]


class TestRepositoryWebhookProcessorValidatePayload:
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


class TestRepositoryWebhookProcessorHandleEvent:
    @pytest.mark.asyncio
    async def test_push_artifact_fetches_and_returns_updated_repository(self, processor, mock_client, mock_exporter):
        payload = {
            "type": HarborEventType.PUSH_ARTIFACT,
            "event_data": {
                "repository": {"namespace": "opensource", "name": "nginx", "repo_full_name": "opensource/nginx"}
            },
        }

        mock_repo = {"name": "nginx", "project_id": 1, "artifact_count": 5}
        mock_exporter.get_resource.return_value = mock_repo

        with patch("harbor.webhooks.processors.repository_webhook_processor.HarborClientFactory") as mock_factory:
            mock_factory.get_client.return_value = mock_client

            with patch(
                "harbor.webhooks.processors.repository_webhook_processor.HarborRepositoryExporter"
            ) as MockExporter:
                MockExporter.return_value = mock_exporter

                result = await processor.handle_event(payload, MagicMock())

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == mock_repo
        assert len(result.deleted_raw_results) == 0

        mock_exporter.get_resource.assert_called_once_with("opensource", "nginx")

    @pytest.mark.asyncio
    async def test_replication_fetches_and_returns_updated_repository(self, processor, mock_client, mock_exporter):
        payload = {
            "type": HarborEventType.REPLICATION,
            "event_data": {"repository": {"namespace": "production", "name": "redis"}},
        }

        mock_repo = {"name": "redis", "project_id": 2}
        mock_exporter.get_resource.return_value = mock_repo

        with patch("harbor.webhooks.processors.repository_webhook_processor.HarborClientFactory") as mock_factory:
            mock_factory.get_client.return_value = mock_client

            with patch(
                "harbor.webhooks.processors.repository_webhook_processor.HarborRepositoryExporter"
            ) as MockExporter:
                MockExporter.return_value = mock_exporter

                result = await processor.handle_event(payload, MagicMock())

        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0

    @pytest.mark.asyncio
    async def test_delete_artifact_fetches_repository_and_returns_updated(self, processor, mock_client, mock_exporter):
        payload = {
            "type": HarborEventType.DELETE_ARTIFACT,
            "event_data": {
                "repository": {"namespace": "staging", "name": "postgres", "repo_full_name": "staging/postgres"}
            },
        }

        mock_repo = {"name": "postgres", "project_id": 3, "artifact_count": 2}
        mock_client.get_repository.return_value = mock_repo

        with patch("harbor.webhooks.processors.repository_webhook_processor.HarborClientFactory") as mock_factory:
            mock_factory.get_client.return_value = mock_client

            with patch(
                "harbor.webhooks.processors.repository_webhook_processor.HarborRepositoryExporter"
            ) as MockExporter:
                MockExporter.return_value = mock_exporter

                result = await processor.handle_event(payload, MagicMock())

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == mock_repo
        assert len(result.deleted_raw_results) == 0

        mock_client.get_repository.assert_called_once_with("staging", "postgres")

    @pytest.mark.asyncio
    async def test_delete_artifact_returns_deleted_when_repository_no_longer_exists(
        self, processor, mock_client, mock_exporter
    ):
        payload = {
            "type": HarborEventType.DELETE_ARTIFACT,
            "event_data": {"repository": {"namespace": "staging", "name": "postgres"}},
        }

        mock_client.get_repository.return_value = None

        with patch("harbor.webhooks.processors.repository_webhook_processor.HarborClientFactory") as mock_factory:
            mock_factory.get_client.return_value = mock_client

            with patch(
                "harbor.webhooks.processors.repository_webhook_processor.HarborRepositoryExporter"
            ) as MockExporter:
                MockExporter.return_value = mock_exporter

                result = await processor.handle_event(payload, MagicMock())

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0]["name"] == "postgres"
        assert result.deleted_raw_results[0]["namespace"] == "staging"

    @pytest.mark.asyncio
    async def test_delete_artifact_returns_updated_when_repository_is_empty(
        self, processor, mock_client, mock_exporter
    ):
        payload = {
            "type": HarborEventType.DELETE_ARTIFACT,
            "event_data": {"repository": {"namespace": "staging", "name": "postgres"}},
        }

        mock_repo = {"name": "postgres", "artifact_count": 0}
        mock_client.get_repository.return_value = mock_repo

        with patch("harbor.webhooks.processors.repository_webhook_processor.HarborClientFactory") as mock_factory:
            mock_factory.get_client.return_value = mock_client

            with patch(
                "harbor.webhooks.processors.repository_webhook_processor.HarborRepositoryExporter"
            ) as MockExporter:
                MockExporter.return_value = mock_exporter

                result = await processor.handle_event(payload, MagicMock())

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["artifact_count"] == 0
        assert len(result.deleted_raw_results) == 0

    @pytest.mark.asyncio
    async def test_returns_empty_results_when_project_name_missing(self, processor, mock_client):
        payload = {"type": HarborEventType.PUSH_ARTIFACT, "event_data": {"repository": {"name": "nginx"}}}

        with patch("harbor.webhooks.processors.repository_webhook_processor.HarborClientFactory") as mock_factory:
            mock_factory.get_client.return_value = mock_client

            result = await processor.handle_event(payload, MagicMock())

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0

    @pytest.mark.asyncio
    async def test_returns_empty_results_when_repository_name_missing(self, processor, mock_client):
        payload = {"type": HarborEventType.PUSH_ARTIFACT, "event_data": {"repository": {"namespace": "opensource"}}}

        with patch("harbor.webhooks.processors.repository_webhook_processor.HarborClientFactory") as mock_factory:
            mock_factory.get_client.return_value = mock_client

            result = await processor.handle_event(payload, MagicMock())

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0

    @pytest.mark.asyncio
    async def test_handles_fetch_failure_gracefully_for_push_artifact(self, processor, mock_client, mock_exporter):
        payload = {
            "type": HarborEventType.PUSH_ARTIFACT,
            "event_data": {"repository": {"namespace": "opensource", "name": "nginx"}},
        }

        mock_exporter.get_resource.side_effect = Exception("API Error")

        with patch("harbor.webhooks.processors.repository_webhook_processor.HarborClientFactory") as mock_factory:
            mock_factory.get_client.return_value = mock_client

            with patch(
                "harbor.webhooks.processors.repository_webhook_processor.HarborRepositoryExporter"
            ) as MockExporter:
                MockExporter.return_value = mock_exporter

                result = await processor.handle_event(payload, MagicMock())

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0

    @pytest.mark.asyncio
    async def test_handles_fetch_failure_gracefully_for_delete_artifact(self, processor, mock_client, mock_exporter):
        payload = {
            "type": HarborEventType.DELETE_ARTIFACT,
            "event_data": {"repository": {"namespace": "opensource", "name": "nginx"}},
        }

        mock_client.get_repository.side_effect = Exception("API Error")

        with patch("harbor.webhooks.processors.repository_webhook_processor.HarborClientFactory") as mock_factory:
            mock_factory.get_client.return_value = mock_client

            with patch(
                "harbor.webhooks.processors.repository_webhook_processor.HarborRepositoryExporter"
            ) as MockExporter:
                MockExporter.return_value = mock_exporter

                result = await processor.handle_event(payload, MagicMock())

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0
