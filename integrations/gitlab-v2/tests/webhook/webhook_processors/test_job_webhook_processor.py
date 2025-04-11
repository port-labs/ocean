import pytest
from unittest.mock import AsyncMock, MagicMock

from gitlab.webhook.webhook_processors.job_webhook_processor import (
    JobWebhookProcessor,
)
from gitlab.helpers.utils import ObjectKind

from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
)

from typing import Any


@pytest.mark.asyncio
class TestJobWebhookProcessor:
    """Test the job webhook processor"""

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        """Create a mock webhook event"""
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Job Hook"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> JobWebhookProcessor:
        """Create a JobWebhookProcessor instance"""
        return JobWebhookProcessor(event=mock_event)

    @pytest.fixture
    def job_payload(self) -> dict[str, Any]:
        """Create a sample job webhook payload"""
        return {
            "object_kind": "build",
            "build_id": 789,
            "build_status": "success",
            "build_started_at": "2021-01-20T09:40:12Z",
            "build_finished_at": "2021-01-20T09:45:12Z",
            "build_duration": 300,
            "build_allow_failure": False,
            "build_stage": "test",
            "project": {
                "id": 456,
                "name": "test-project",
                "web_url": "https://gitlab.com/test/test-project",
            },
            "repository": {
                "name": "test-project",
                "url": "git@gitlab.com:test/test-project.git",
                "description": "Test project",
                "homepage": "https://gitlab.com/test/test-project",
            },
            "commit": {
                "id": "abc123",
                "message": "Test commit",
                "timestamp": "2021-01-20T09:35:12Z",
                "url": "https://gitlab.com/test/test-project/-/commit/abc123",
            },
        }

    async def test_get_matching_kinds(
        self, processor: JobWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        """Test that get_matching_kinds returns the JOB kind."""
        assert await processor.get_matching_kinds(mock_event) == [ObjectKind.JOB]

    async def test_handle_event(
        self, processor: JobWebhookProcessor, job_payload: dict[str, Any]
    ) -> None:
        """Test handling a job event"""
        resource_config = MagicMock()
        job_id = job_payload["build_id"]
        project_id = job_payload["project"]["id"]

        expected_job = {
            "id": job_id,
            "project_id": project_id,
            "status": job_payload["build_status"],
            "stage": job_payload["build_stage"],
            "started_at": job_payload["build_started_at"],
            "finished_at": job_payload["build_finished_at"],
            "duration": job_payload["build_duration"],
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_job = AsyncMock(return_value=expected_job)

        result = await processor.handle_event(job_payload, resource_config)

        processor._gitlab_webhook_client.get_job.assert_called_once_with(
            project_id, job_id
        )
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == expected_job
        assert not result.deleted_raw_results

    async def test_should_process_event(self, processor: JobWebhookProcessor) -> None:
        """Test that should_process_event correctly identifies job events"""
        # Valid job event
        valid_event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Job Hook"},
            payload={"object_kind": "build"},
        )
        assert await processor.should_process_event(valid_event) is True

        # Invalid event type
        invalid_event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Pipeline Hook"},
            payload={"object_kind": "build"},
        )
        assert await processor.should_process_event(invalid_event) is False

        # Invalid object_kind
        invalid_kind_event = WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Job Hook"},
            payload={"object_kind": "pipeline"},
        )
        assert await processor.should_process_event(invalid_kind_event) is False
