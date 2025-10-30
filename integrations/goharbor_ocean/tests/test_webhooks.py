import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)

from harbor.webhooks.processor import (
    ArtifactWebhookProcessor,
    RepositoryWebhookProcessor,
)
from harbor.webhooks import events


@pytest.fixture
def artifact_push_webhook_payload():
    return {
        "type": "PUSH_ARTIFACT",
        "occur_at": 1586922308,
        "operator": "admin",
        "event_data": {
            "resources": [
                {
                    "digest": "sha256:abc123",
                    "tag": "latest",
                    "resource_url": "harbor.example.com/test/nginx:latest",
                }
            ],
            "repository": {
                "name": "nginx",
                "namespace": "test",
                "repo_full_name": "test/nginx",
                "repo_type": "image",
            },
        },
    }


@pytest.fixture
def artifact_delete_webhook_payload():
    return {
        "type": "DELETE_ARTIFACT",
        "occur_at": 1586922308,
        "operator": "admin",
        "event_data": {
            "resources": [{"digest": "sha256:abc123", "tag": "latest"}],
            "repository": {
                "name": "nginx",
                "namespace": "test",
                "repo_full_name": "test/nginx",
                "repo_type": "image",
            },
        },
    }


@pytest.fixture
def scanning_completed_webhook_payload():
    return {
        "type": "SCANNING_COMPLETED",
        "occur_at": 1586922308,
        "operator": "admin",
        "event_data": {
            "resources": [
                {
                    "digest": "sha256:abc123",
                    "tag": "latest",
                    "scan_overview": {"severity": "High", "total_count": 5},
                }
            ],
            "repository": {
                "name": "nginx",
                "namespace": "test",
                "repo_full_name": "test/nginx",
                "repo_type": "image",
            },
        },
    }


class TestArtifactWebhookProcessor:
    @pytest.mark.asyncio
    async def test_should_process_artifact_push_event(
        self, artifact_push_webhook_payload
    ):
        """Test processor correctly identifies artifact push events."""
        event = WebhookEvent(
            trace_id='1a673b4c-08c3-46cd-afcb-cda9a6fc8257', # uuid string
            payload=artifact_push_webhook_payload,
            headers={}
        )
        processor = ArtifactWebhookProcessor(event)

        should_process = await processor.should_process_event(event)

        assert should_process is True

    @pytest.mark.asyncio
    async def test_should_process_artifact_delete_event(
        self, artifact_delete_webhook_payload
    ):
        """Test processor correctly identifies artifact delete events"""
        event = WebhookEvent(
            trace_id='trace_id_12345',
            payload=artifact_delete_webhook_payload,
            headers={}
        )
        processor = ArtifactWebhookProcessor(event)

        should_process = await processor.should_process_event(event)

        assert should_process is True

    @pytest.mark.asyncio
    async def test_should_not_process_non_artifact_event(self):
        """Test processor ignores non-artifact events"""
        non_artifact_payload = {"type": "QUOTA_EXCEED", "event_data": {}}
        event = WebhookEvent(
            trace_id='trace_id_67890',
            payload=non_artifact_payload,
            headers={}
        )
        processor = ArtifactWebhookProcessor(event)

        should_process = await processor.should_process_event(event)

        assert should_process is False

    @pytest.mark.asyncio
    async def test_get_matching_kinds_returns_artifact(
        self, artifact_push_webhook_payload
    ):
        """Test processor returns correct resource kind"""
        event = WebhookEvent(
            trace_id='trace_id_54321',
            payload=artifact_push_webhook_payload,
            headers={}
        )
        processor = ArtifactWebhookProcessor(event)

        kinds = await processor.get_matching_kinds(event)

        assert kinds == ["artifact"]

    @pytest.mark.asyncio
    async def test_handle_artifact_push_event_fetches_fresh_data(
        self, artifact_push_webhook_payload
    ):
        """Test artifact push event fetches updated data from GoHarbor"""
        event = WebhookEvent(
            trace_id="2f97ecdc-216c-4bde-823f-15ae968ea3c7",
            payload=artifact_push_webhook_payload,
            headers={},
        )
        processor = ArtifactWebhookProcessor(event)
        mock_client = MagicMock()

        async def mock_artifacts():
            yield [{"id": 1, "digest": "sha256:abc123", "tags": [{"name": "latest"}]}]

        mock_client.get_paginated_resources = MagicMock(return_value=mock_artifacts())

        with patch(
            "harbor.factory.HarborClientFactory.get_client",
            return_value=mock_client,
        ):
            result = await processor.handle_event(
                artifact_push_webhook_payload, MagicMock()
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["digest"] == "sha256:abc123"
        assert len(result.deleted_raw_results) == 0

    @pytest.mark.asyncio
    async def test_handle_artifact_delete_event_returns_deleted_resources(
        self, artifact_delete_webhook_payload
    ):
        event = WebhookEvent(
            trace_id="3e5f4a1b-9c4d-4f2e-8c3d-7b6e5f4a1b9c",
            payload=artifact_delete_webhook_payload,
            headers={},
        )
        processor = ArtifactWebhookProcessor(event)

        result = await processor.handle_event(
            artifact_delete_webhook_payload, MagicMock()
        )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0]["digest"] == "sha256:abc123"
        assert len(result.updated_raw_results) == 0

    @pytest.mark.asyncio
    async def test_handle_event_with_missing_repository_info(self):
        """Test processor handles missing repository information gracefully."""
        invalid_payload = {
            "type": "PUSH_ARTIFACT",
            "event_data": {"resources": [], "repository": {}},
        }
        event = WebhookEvent(
            trace_id='sample-test-tracer-id-eyes',
            payload=invalid_payload,
            headers={},
        )
        processor = ArtifactWebhookProcessor(event)

        result = await processor.handle_event(invalid_payload, MagicMock())

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0

    @pytest.mark.asyncio
    async def test_handle_scanning_completed_event(
        self, scanning_completed_webhook_payload
    ):
        """Test scanning completed event fetches updated artifact with scan results."""
        event = WebhookEvent(
            trace_id='test-trace-id-4567',
            payload=scanning_completed_webhook_payload,
            headers={},
        )
        processor = ArtifactWebhookProcessor(event)
        mock_client = MagicMock()

        async def mock_artifacts_with_scan():
            yield [
                {
                    "id": 1,
                    "digest": "sha256:abc123",
                    "scan_overview": {"severity": "High", "total_count": 5},
                }
            ]

        mock_client.get_paginated_resources = MagicMock(
            return_value=mock_artifacts_with_scan()
        )

        with patch(
            "harbor.factory.HarborClientFactory.get_client",
            return_value=mock_client,
        ):
            result = await processor.handle_event(
                scanning_completed_webhook_payload, MagicMock()
            )

        assert len(result.updated_raw_results) == 1
        assert "scan_overview" in result.updated_raw_results[0]

    @pytest.mark.asyncio
    async def test_validate_payload_with_valid_structure(
        self, artifact_push_webhook_payload
    ):
        """Test payload validation accepts valid webhook structure."""
        event = WebhookEvent(
            trace_id='valid-structure-trace-id',
            payload=artifact_push_webhook_payload,
            headers={},
        )
        processor = ArtifactWebhookProcessor(event)

        is_valid = await processor.validate_payload(artifact_push_webhook_payload)

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_payload_with_invalid_structure(self):
        """Test payload validation rejects invalid webhook structure."""
        invalid_payload = {"invalid": "payload"}
        event = WebhookEvent(
            trace_id='invalid-structure-trace-id',
            payload=invalid_payload,
            headers={},
        )
        processor = ArtifactWebhookProcessor(event)

        is_valid = await processor.validate_payload(invalid_payload)

        assert is_valid is False


class TestRepositoryWebhookProcessor:
    @pytest.mark.asyncio
    async def test_should_process_repository_event(self, artifact_push_webhook_payload):
        """Test processor correcty identifies repository-affecting events"""
        event = WebhookEvent(
            trace_id='repo-event-trace-id-890',
            payload=artifact_push_webhook_payload,
            headers={}
        )
        processor = RepositoryWebhookProcessor(event)

        should_process = await processor.should_process_event(event)

        assert should_process is True

    @pytest.mark.asyncio
    async def test_get_matching_kinds_returns_repository(
        self, artifact_push_webhook_payload
    ):
        """Test processor returns repository kind"""
        event = WebhookEvent(
            trace_id='repo-kind-trace-id-321',
            payload=artifact_push_webhook_payload,
            headers={}
        )
        processor = RepositoryWebhookProcessor(event)

        kinds = await processor.get_matching_kinds(event)

        assert kinds == ["repository"]

    @pytest.mark.asyncio
    async def test_handle_repository_event_fetches_repository_data(
        self, artifact_push_webhook_payload
    ):
        """Test repository event fetches updated repository information"""
        event = WebhookEvent(
            trace_id='handle-repo-event-trace-id-654',
            payload=artifact_push_webhook_payload,
            headers={},
        )
        processor = RepositoryWebhookProcessor(event)
        mock_client = MagicMock()

        async def mock_repositories():
            yield [{"id": 1, "name": "test/nginx", "artifact_count": 5}]

        mock_client.get_paginated_resources = MagicMock(
            return_value=mock_repositories()
        )

        with patch(
            "harbor.factory.HarborClientFactory.get_client",
            return_value=mock_client,
        ):
            result = await processor.handle_event(
                artifact_push_webhook_payload, MagicMock()
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["name"] == "test/nginx"


@pytest.mark.asyncio
async def test_multiple_processors_handle_same_event_independently(
    artifact_push_webhook_payload,
):
    """Test that multiple processors can process the same webhook event"""
    event = WebhookEvent(
        trace_id='multi-processor-trace-id-111',
        payload=artifact_push_webhook_payload,
        headers={},
    )
    artifact_processor = ArtifactWebhookProcessor(event)
    repository_processor = RepositoryWebhookProcessor(event)

    artifact_should_process = await artifact_processor.should_process_event(event)
    repository_should_process = await repository_processor.should_process_event(event)

    assert artifact_should_process is True
    assert repository_should_process is True
