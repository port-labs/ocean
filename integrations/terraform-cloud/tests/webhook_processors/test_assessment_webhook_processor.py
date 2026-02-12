from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from webhook_processors.assessment_webhook_processor import AssessmentWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from utils import ObjectKind


@pytest.fixture
def processor() -> Any:
    mock_event = MagicMock(spec=WebhookEvent)
    return AssessmentWebhookProcessor(mock_event)


class TestGetMatchingKinds:
    @pytest.mark.asyncio
    async def test_get_matching_kinds_returns_workspace(self, processor: Any) -> None:
        event = MagicMock()

        result = await processor.get_matching_kinds(event)

        assert result == [ObjectKind.HEALTH_ASSESSMENT]
        assert len(result) == 1


class TestShouldProcessEvent:
    @pytest.mark.asyncio
    async def test_should_process_event_always_returns_true(
        self, processor: Any
    ) -> None:
        event = MagicMock()
        event.payload = {"notifications": [{"run_status": "planning"}]}

        result = await processor._should_process_event(event)

        assert result is True

    @pytest.mark.asyncio
    async def test_should_process_event_with_different_payloads(
        self, processor: Any
    ) -> None:
        events = [
            {"notifications": [{"run_status": "applied"}]},
            {"notifications": [{"run_status": "errored"}]},
            {"notifications": []},
        ]

        for event_payload in events:
            event = MagicMock()
            event.payload = event_payload
            result = await processor._should_process_event(event)
            assert result is True


class TestHandleEvent:
    @pytest.mark.asyncio
    async def test_handle_event_success(self, processor: Any) -> None:
        payload: dict[str, Any] = {"workspace_id": "ws-123"}
        resource_config = MagicMock()

        assessment_data = {
            "id": "ws-123",
            "attributes": {"name": "test-workspace"},
        }

        mock_client = MagicMock()
        mock_client.get_current_health_assessment_for_workspace = AsyncMock(
            return_value=assessment_data
        )

        with patch(
            "webhook_processors.assessment_webhook_processor.init_terraform_client"
        ) as mock_init:
            mock_init.return_value = mock_client

            result = await processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert len(result.updated_raw_results) == 1
            assert result.updated_raw_results[0] == assessment_data
            assert result.deleted_raw_results == []
            mock_client.get_current_health_assessment_for_workspace.assert_called_once_with(
                "ws-123"
            )

    @pytest.mark.asyncio
    async def test_handle_event_calls_init_terraform_client(
        self, processor: Any
    ) -> None:
        payload: dict[str, Any] = {"workspace_id": "ws-123"}
        resource_config = MagicMock()

        workspace_data = {"id": "ws-123"}

        mock_client = MagicMock()
        mock_client.get_current_health_assessment_for_workspace = AsyncMock(
            return_value=workspace_data
        )

        with patch(
            "webhook_processors.assessment_webhook_processor.init_terraform_client"
        ) as mock_init:
            mock_init.return_value = mock_client

            await processor.handle_event(payload, resource_config)

            mock_init.assert_called_once()
