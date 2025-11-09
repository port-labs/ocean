from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from webhook_processors.run_webhook_processor import RunWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from utils import ObjectKind


@pytest.fixture
def processor() -> Any:
    mock_event = MagicMock(spec=WebhookEvent)
    return RunWebhookProcessor(mock_event)


class TestGetMatchingKinds:
    @pytest.mark.asyncio
    async def test_get_matching_kinds_returns_run(self, processor: Any) -> None:
        event = MagicMock()

        result = await processor.get_matching_kinds(event)

        assert result == [ObjectKind.RUN]
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
            {"notifications": [{"run_status": "planning"}]},
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
        payload: dict[str, Any] = {"run_id": "run-123"}
        resource_config = MagicMock()

        run_data = {
            "id": "run-123",
            "attributes": {"status": "applied"},
        }

        mock_client = MagicMock()
        mock_client.get_single_run = AsyncMock(return_value=run_data)

        with patch(
            "webhook_processors.run_webhook_processor.init_terraform_client"
        ) as mock_init:
            mock_init.return_value = mock_client

            result = await processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert len(result.updated_raw_results) == 1
            assert result.updated_raw_results[0] == run_data
            assert result.deleted_raw_results == []
            mock_client.get_single_run.assert_called_once_with("run-123")

    @pytest.mark.asyncio
    async def test_handle_event_with_different_run_statuses(
        self, processor: Any
    ) -> None:
        statuses = ["applied", "planning", "errored", "completed"]

        for status in statuses:
            payload: dict[str, Any] = {"run_id": f"run-{status}"}
            resource_config = MagicMock()

            run_data = {
                "id": f"run-{status}",
                "attributes": {"status": status},
            }

            mock_client = MagicMock()
            mock_client.get_single_run = AsyncMock(return_value=run_data)

            with patch(
                "webhook_processors.run_webhook_processor.init_terraform_client"
            ) as mock_init:
                mock_init.return_value = mock_client

                result = await processor.handle_event(payload, resource_config)

                assert result.updated_raw_results[0]["attributes"]["status"] == status

    @pytest.mark.asyncio
    async def test_handle_event_preserves_run_data(self, processor: Any) -> None:
        payload: dict[str, Any] = {
            "run_id": "run-456",
            "extra_field": "should_be_ignored",
        }
        resource_config = MagicMock()

        run_data = {
            "id": "run-456",
            "attributes": {
                "status": "applied",
                "message": "Test run",
                "created-at": "2024-01-01T00:00:00Z",
            },
            "relationships": {
                "workspace": {"data": {"id": "ws-1"}},
                "plan": {"data": {"id": "plan-1"}},
            },
        }

        mock_client = MagicMock()
        mock_client.get_single_run = AsyncMock(return_value=run_data)

        with patch(
            "webhook_processors.run_webhook_processor.init_terraform_client"
        ) as mock_init:
            mock_init.return_value = mock_client

            result = await processor.handle_event(payload, resource_config)

            assert result.updated_raw_results[0]["id"] == "run-456"
            assert result.updated_raw_results[0]["attributes"]["status"] == "applied"
            assert result.updated_raw_results[0]["attributes"]["message"] == "Test run"
            assert (
                result.updated_raw_results[0]["relationships"]["workspace"]["data"][
                    "id"
                ]
                == "ws-1"
            )

    @pytest.mark.asyncio
    async def test_handle_event_calls_init_terraform_client(
        self, processor: Any
    ) -> None:
        payload: dict[str, Any] = {"run_id": "run-789"}
        resource_config = MagicMock()

        run_data = {"id": "run-789"}

        mock_client = MagicMock()
        mock_client.get_single_run = AsyncMock(return_value=run_data)

        with patch(
            "webhook_processors.run_webhook_processor.init_terraform_client"
        ) as mock_init:
            mock_init.return_value = mock_client

            await processor.handle_event(payload, resource_config)

            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_event_returns_empty_deleted_results(
        self, processor: Any
    ) -> None:
        payload: dict[str, Any] = {"run_id": "run-123"}
        resource_config = MagicMock()

        run_data = {"id": "run-123"}

        mock_client = MagicMock()
        mock_client.get_single_run = AsyncMock(return_value=run_data)

        with patch(
            "webhook_processors.run_webhook_processor.init_terraform_client"
        ) as mock_init:
            mock_init.return_value = mock_client

            result = await processor.handle_event(payload, resource_config)

            assert result.deleted_raw_results == []
            assert isinstance(result.deleted_raw_results, list)

    @pytest.mark.asyncio
    async def test_handle_event_with_minimal_run_data(self, processor: Any) -> None:
        payload: dict[str, Any] = {"run_id": "run-minimal"}
        resource_config = MagicMock()

        run_data = {"id": "run-minimal"}

        mock_client = MagicMock()
        mock_client.get_single_run = AsyncMock(return_value=run_data)

        with patch(
            "webhook_processors.run_webhook_processor.init_terraform_client"
        ) as mock_init:
            mock_init.return_value = mock_client

            result = await processor.handle_event(payload, resource_config)

            assert len(result.updated_raw_results) == 1
            assert result.updated_raw_results[0]["id"] == "run-minimal"
