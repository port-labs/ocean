from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from webhook_processors.state_file_webhook_processor import StateFileWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from utils import ObjectKind


@pytest.fixture
def processor() -> Any:
    mock_event = MagicMock(spec=WebhookEvent)
    return StateFileWebhookProcessor(mock_event)


@pytest.fixture
def mock_webhook_event() -> Any:
    event = MagicMock(spec=WebhookEvent)
    event.payload = {
        "notifications": [{"trigger": "run:completed", "run_status": "applied"}],
        "workspace_name": "test-workspace",
        "organization_name": "test-org",
    }
    return event


class TestGetMatchingKinds:
    @pytest.mark.asyncio
    async def test_get_matching_kinds_returns_state_file(self, processor: Any) -> None:
        event = MagicMock()

        result = await processor.get_matching_kinds(event)

        assert result == [ObjectKind.STATE_FILE]
        assert len(result) == 1


class TestShouldProcessEvent:
    @pytest.mark.asyncio
    async def test_should_process_event_applied_status(self, processor: Any) -> None:
        event = MagicMock()
        event.payload = {"notifications": [{"run_status": "applied"}]}

        result = await processor._should_process_event(event)

        assert result is True

    @pytest.mark.asyncio
    async def test_should_process_event_not_applied_status(
        self, processor: Any
    ) -> None:
        event = MagicMock()
        event.payload = {"notifications": [{"run_status": "planning"}]}

        result = await processor._should_process_event(event)

        assert result is False

    @pytest.mark.asyncio
    async def test_should_process_event_multiple_notifications_with_applied(
        self, processor: Any
    ) -> None:
        event = MagicMock()
        event.payload = {
            "notifications": [
                {"run_status": "planning"},
                {"run_status": "applied"},
            ]
        }

        result = await processor._should_process_event(event)

        assert result is True

    @pytest.mark.asyncio
    async def test_should_process_event_multiple_notifications_no_applied(
        self, processor: Any
    ) -> None:
        event = MagicMock()
        event.payload = {
            "notifications": [
                {"run_status": "planning"},
                {"run_status": "errored"},
            ]
        }

        result = await processor._should_process_event(event)

        assert result is False

    @pytest.mark.asyncio
    async def test_should_process_event_empty_notifications(
        self, processor: Any
    ) -> None:
        event = MagicMock()
        event.payload = {"notifications": []}

        result = await processor._should_process_event(event)

        assert result is False


class TestHandleEvent:
    @pytest.mark.asyncio
    async def test_handle_event_success(self, processor: Any) -> None:
        payload: dict[str, Any] = {
            "workspace_name": "test-workspace",
            "organization_name": "test-org",
        }
        resource_config = MagicMock()
        state_files = [
            {"version": 4, "resources": []},
            {"version": 4, "resources": [{"type": "aws_instance"}]},
        ]

        mock_client = MagicMock()

        async def mock_state_files(workspace_name: str, organization_name: str) -> Any:
            yield state_files

        mock_client.get_state_file_for_single_workspace = mock_state_files

        with patch(
            "webhook_processors.state_file_webhook_processor.init_terraform_client"
        ) as mock_init:
            mock_init.return_value = mock_client

            result = await processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert len(result.updated_raw_results) == 2
            assert result.deleted_raw_results == []
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_event_no_state_files(self, processor: Any) -> None:
        payload: dict[str, Any] = {
            "workspace_name": "test-workspace",
            "organization_name": "test-org",
        }
        resource_config = MagicMock()

        mock_client = MagicMock()

        async def mock_state_files(workspace_name: str, organization_name: str) -> Any:
            yield []

        mock_client.get_state_file_for_single_workspace = mock_state_files

        with patch(
            "webhook_processors.state_file_webhook_processor.init_terraform_client"
        ) as mock_init:
            mock_init.return_value = mock_client

            result = await processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert len(result.updated_raw_results) == 0
            assert result.deleted_raw_results == []

    @pytest.mark.asyncio
    async def test_handle_event_multiple_batches(self, processor: Any) -> None:
        payload: dict[str, Any] = {
            "workspace_name": "test-workspace",
            "organization_name": "test-org",
        }
        resource_config = MagicMock()

        mock_client = MagicMock()

        async def mock_state_files(workspace_name: str, organization_name: str) -> Any:
            yield [{"version": 4, "resources": []}]
            yield [{"version": 4, "resources": [{"type": "aws_s3_bucket"}]}]

        mock_client.get_state_file_for_single_workspace = mock_state_files

        with patch(
            "webhook_processors.state_file_webhook_processor.init_terraform_client"
        ) as mock_init:
            mock_init.return_value = mock_client

            result = await processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert len(result.updated_raw_results) == 2
            assert result.deleted_raw_results == []

    @pytest.mark.asyncio
    async def test_handle_event_extracts_correct_payload_fields(
        self, processor: Any
    ) -> None:
        payload: dict[str, Any] = {
            "workspace_name": "my-workspace",
            "organization_name": "my-org",
            "run_id": "run-123",
        }
        resource_config = MagicMock()

        mock_client = MagicMock()

        async def mock_state_files(workspace_name: str, organization_name: str) -> Any:
            yield []

        mock_state_files_wrapped = MagicMock(side_effect=mock_state_files)
        mock_client.get_state_file_for_single_workspace = mock_state_files_wrapped

        with patch(
            "webhook_processors.state_file_webhook_processor.init_terraform_client"
        ) as mock_init:
            mock_init.return_value = mock_client

            await processor.handle_event(payload, resource_config)

            mock_state_files_wrapped.assert_called_once_with("my-workspace", "my-org")
