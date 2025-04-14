import pytest
from unittest.mock import AsyncMock, MagicMock

from gitlab.webhook.webhook_processors.pipeline_webhook_processor import (
    PipelineWebhookProcessor,
)
from gitlab.helpers.utils import ObjectKind

from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)

from typing import Any


@pytest.mark.asyncio
class TestPipelineWebhookProcessor:
    """Test the pipeline webhook processor"""

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        """Create a mock webhook event"""
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Pipeline Hook"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> PipelineWebhookProcessor:
        """Create a PipelineWebhookProcessor instance"""
        return PipelineWebhookProcessor(event=mock_event)

    @pytest.fixture
    def pipeline_payload(self) -> dict[str, Any]:
        """Create a sample pipeline webhook payload"""
        return {
            "object_kind": "pipeline",
            "object_attributes": {
                "id": 123,
                "ref": "main",
                "status": "success",
                "stages": ["build", "test", "deploy"],
                "created_at": "2021-01-20T09:40:12Z",
                "updated_at": "2021-01-20T09:45:12Z",
            },
            "project": {
                "id": 456,
                "name": "test-project",
                "web_url": "https://gitlab.com/test/test-project",
            },
        }

    async def test_get_matching_kinds(
        self, processor: PipelineWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        """Test that get_matching_kinds returns the PIPELINE kind."""
        assert await processor.get_matching_kinds(mock_event) == [ObjectKind.PIPELINE]

    async def test_handle_event(
        self, processor: PipelineWebhookProcessor, pipeline_payload: dict[str, Any]
    ) -> None:
        """Test handling a pipeline event"""
        resource_config = MagicMock()
        pipeline_id = pipeline_payload["object_attributes"]["id"]
        project_id = pipeline_payload["project"]["id"]

        expected_pipeline = {
            "id": pipeline_id,
            "project_id": project_id,
            "ref": pipeline_payload["object_attributes"]["ref"],
            "status": pipeline_payload["object_attributes"]["status"],
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_pipeline = AsyncMock(
            return_value=expected_pipeline
        )

        result = await processor.handle_event(pipeline_payload, resource_config)

        processor._gitlab_webhook_client.get_pipeline.assert_called_once_with(
            project_id, pipeline_id
        )
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == expected_pipeline
        assert not result.deleted_raw_results

    async def test_should_process_event(
        self, processor: PipelineWebhookProcessor
    ) -> None:
        """Test that should_process_event correctly identifies pipeline events"""
        # Valid pipeline event
        valid_event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Pipeline Hook"},
            payload={"object_kind": "pipeline"},
        )
        assert await processor.should_process_event(valid_event) is True

        # Invalid event type
        invalid_event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Job Hook"},
            payload={"object_kind": "pipeline"},
        )
        assert await processor.should_process_event(invalid_event) is False

        # Invalid object_kind
        invalid_kind_event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Pipeline Hook"},
            payload={"object_kind": "job"},
        )
        assert await processor.should_process_event(invalid_kind_event) is False
