import pytest
import respx
from httpx import Response
from unittest.mock import patch
from uuid import uuid4
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from webhook_processors.artifact_webhook_processor import ArtifactWebhookProcessor


class TestArtifactWebhookProcessor:
    """Tests for ArtifactWebhookProcessor."""

    @pytest.mark.asyncio
    async def test_should_process_artifact_pushed_event(
        self, mock_webhook_artifact_pushed
    ):
        """Test that artifact pushed events are recognized."""
        event = WebhookEvent(
            trace_id=str(uuid4()),
            payload=mock_webhook_artifact_pushed,
            headers={},
        )
        processor = ArtifactWebhookProcessor(event)

        should_process = await processor.should_process_event(event)

        assert should_process is True

    @pytest.mark.asyncio
    async def test_should_process_artifact_deleted_event(
        self, mock_webhook_artifact_deleted
    ):
        """Test that artifact deleted events are recognized."""
        event = WebhookEvent(
            trace_id=str(uuid4()),
            payload=mock_webhook_artifact_deleted,
            headers={},
        )
        processor = ArtifactWebhookProcessor(event)

        should_process = await processor.should_process_event(event)

        assert should_process is True

    @pytest.mark.asyncio
    async def test_should_not_process_non_artifact_event(self):
        """Test that non-artifact events are not processed."""
        event = WebhookEvent(
            trace_id=str(uuid4()),
            payload={"type": "harbor.project.created"},
            headers={},
        )
        processor = ArtifactWebhookProcessor(event)

        should_process = await processor.should_process_event(event)

        assert should_process is False

    @pytest.mark.asyncio
    async def test_get_matching_kinds(self, mock_webhook_artifact_pushed):
        """Test that correct kinds are returned."""
        event = WebhookEvent(
            trace_id=str(uuid4()),
            payload=mock_webhook_artifact_pushed,
            headers={},
        )
        processor = ArtifactWebhookProcessor(event)

        kinds = await processor.get_matching_kinds(event)

        assert kinds == ["artifact"]

    @pytest.mark.asyncio
    async def test_validate_payload_valid(self, mock_webhook_artifact_pushed):
        """Test payload validation with valid data."""
        event = WebhookEvent(
            trace_id=str(uuid4()),
            payload=mock_webhook_artifact_pushed,
            headers={},
        )
        processor = ArtifactWebhookProcessor(event)

        is_valid = await processor.validate_payload(mock_webhook_artifact_pushed)

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_payload_missing_data(self):
        """Test payload validation with missing data."""
        invalid_payload = {"type": "harbor.artifact.pushed"}
        event = WebhookEvent(
            trace_id=str(uuid4()),
            payload=invalid_payload,
            headers={},
        )
        processor = ArtifactWebhookProcessor(event)

        is_valid = await processor.validate_payload(invalid_payload)

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validate_payload_missing_resources(self):
        """Test payload validation with missing resources."""
        invalid_payload = {
            "type": "harbor.artifact.pushed",
            "data": {"repository": {}},
        }
        event = WebhookEvent(
            trace_id=str(uuid4()),
            payload=invalid_payload,
            headers={},
        )
        processor = ArtifactWebhookProcessor(event)

        is_valid = await processor.validate_payload(invalid_payload)

        assert is_valid is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_handle_artifact_pushed_event(
        self, mock_webhook_artifact_pushed, mock_artifact_data, mock_harbor_config
    ):
        """Test handling artifact pushed event."""
        event = WebhookEvent(
            trace_id=str(uuid4()),
            payload=mock_webhook_artifact_pushed,
            headers={},
        )
        processor = ArtifactWebhookProcessor(event)

        # Mock Harbor API call to fetch artifact details
        respx.get(
            "http://localhost:8081/api/v2.0/projects/ocean-integration/repositories/redis/artifacts/e19a92f6821ebdbfa"
            "6676b7133c594c7ea9c3702daf773f5064845b9f8642b93"
        ).mock(return_value=Response(200, json=mock_artifact_data[0]))

        # Mock create_harbor_client to return a mock client with get_artifact method
        with patch(
            "webhook_processors.artifact_webhook_processor.create_harbor_client"
        ) as mock_init:
            # Create a mock client
            mock_client = type(
                "MockClient", (), {"get_artifact": lambda *args, **kwargs: None}
            )()

            # Make get_artifact async and return mock data with enrichment
            async def mock_get_artifact(
                project_name, repository_name, reference, params=None
            ):
                artifact_ = mock_artifact_data[0].copy()
                artifact_["_project_name"] = project_name
                artifact_["_repository_name"] = repository_name
                artifact_["_repository_full_name"] = f"{project_name}/{repository_name}"
                return artifact_

            mock_client.get_artifact = mock_get_artifact
            mock_init.return_value = mock_client

            # Handle the event
            result = await processor.handle_event(
                payload=mock_webhook_artifact_pushed,
                resource_config=None,
            )

            assert len(result.updated_raw_results) == 1
            assert len(result.deleted_raw_results) == 0

            artifact = result.updated_raw_results[0]
            assert artifact["_project_name"] == "ocean-integration"
            assert artifact["_repository_name"] == "redis"

    @pytest.mark.asyncio
    async def test_handle_artifact_deleted_event(self, mock_webhook_artifact_deleted):
        """Test handling artifact deleted event."""
        event = WebhookEvent(
            trace_id=str(uuid4()),
            payload=mock_webhook_artifact_deleted,
            headers={},
        )
        processor = ArtifactWebhookProcessor(event)

        # Mock create_harbor_client (not needed for delete)
        with patch(
            "webhook_processors.artifact_webhook_processor.create_harbor_client"
        ):
            # Handle the event
            result = await processor.handle_event(
                payload=mock_webhook_artifact_deleted,
                resource_config=None,
            )

            assert len(result.updated_raw_results) == 0
            assert len(result.deleted_raw_results) == 1

            artifact = result.deleted_raw_results[0]
            assert (
                artifact["digest"]
                == "sha256:e19a92f6821ebdbfa6676b7133c594c7ea9c3702daf773f5064845b9f8642b93"
            )
            assert artifact["_project_name"] == "ocean-integration"
            assert artifact["_repository_name"] == "redis"
