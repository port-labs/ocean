from typing import Any
import pytest
from unittest.mock import MagicMock
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from checkmarx_one.core.webhook_processors.project_webhook_processor import (
    ProjectWebhookProcessor,
)


class TestProjectWebhookProcessor:
    @pytest.fixture
    def processor(self) -> ProjectWebhookProcessor:
        return ProjectWebhookProcessor()  # type: ignore

    @pytest.fixture
    def valid_project_payload(self) -> dict[str, Any]:
        return {
            "event_type": "Project Created",
            "project": {
                "id": "test-project-id",
                "name": "Test Project",
                "description": "A test project",
            },
        }

    @pytest.fixture
    def invalid_payload(self) -> dict[str, Any]:
        return {
            "event_type": "Completed Scan",  # Wrong event type
            "scan": {"id": "test-scan-id"},
        }

    @pytest.mark.asyncio
    async def test_should_process_event_valid_project(
        self, processor: ProjectWebhookProcessor, valid_project_payload: dict[str, Any]
    ) -> None:
        """Test that project creation events are processed."""
        event = WebhookEvent(
            payload=valid_project_payload, headers={}, _original_request=MagicMock()
        )  # type: ignore

        result = await processor._should_process_event(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_process_event_invalid_event(
        self, processor: ProjectWebhookProcessor, invalid_payload: dict[str, Any]
    ) -> None:
        """Test that non-project events are not processed."""
        event = WebhookEvent(
            payload=invalid_payload, headers={}, _original_request=MagicMock()
        )  # type: ignore

        result = await processor._should_process_event(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_matching_kinds(self, processor: ProjectWebhookProcessor) -> None:
        """Test that the processor returns the correct resource kind."""
        event = WebhookEvent(
            payload={}, headers={}, _original_request=MagicMock()
        )  # type: ignore

        kinds = await processor.get_matching_kinds(event)
        assert kinds == ["project"]

    @pytest.mark.asyncio
    async def test_validate_payload_valid(
        self, processor: ProjectWebhookProcessor, valid_project_payload: dict[str, Any]
    ) -> None:
        """Test that valid project payloads are accepted."""
        result = await processor.validate_payload(valid_project_payload)
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_payload_invalid(
        self, processor: ProjectWebhookProcessor, invalid_payload: dict[str, Any]
    ) -> None:
        """Test that invalid payloads are rejected."""
        result = await processor.validate_payload(invalid_payload)
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_payload_missing_fields(
        self, processor: ProjectWebhookProcessor
    ) -> None:
        """Test that payloads missing required fields are rejected."""
        incomplete_payload = {"event_type": "Project Created"}  # Missing project
        result = await processor.validate_payload(incomplete_payload)
        assert result is False
