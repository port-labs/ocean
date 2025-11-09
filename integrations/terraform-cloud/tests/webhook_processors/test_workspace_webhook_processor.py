from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from webhook_processors.workspace_webhook_processor import WorkspaceWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from utils import ObjectKind


@pytest.fixture
def processor() -> Any:
    mock_event = MagicMock(spec=WebhookEvent)
    return WorkspaceWebhookProcessor(mock_event)


class TestGetMatchingKinds:
    @pytest.mark.asyncio
    async def test_get_matching_kinds_returns_workspace(self, processor: Any) -> None:
        event = MagicMock()

        result = await processor.get_matching_kinds(event)

        assert result == [ObjectKind.WORKSPACE]
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

        workspace_data = {
            "id": "ws-123",
            "attributes": {"name": "test-workspace"},
        }
        enriched_workspace = {
            "id": "ws-123",
            "attributes": {"name": "test-workspace"},
            "__tags": [{"id": "tag-1"}],
        }

        mock_client = MagicMock()
        mock_client.get_single_workspace = AsyncMock(return_value=workspace_data)

        with (
            patch(
                "webhook_processors.workspace_webhook_processor.init_terraform_client"
            ) as mock_init,
            patch(
                "webhook_processors.workspace_webhook_processor.enrich_workspace_with_tags",
                new_callable=AsyncMock,
            ) as mock_enrich,
        ):
            mock_init.return_value = mock_client
            mock_enrich.return_value = enriched_workspace

            result = await processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert len(result.updated_raw_results) == 1
            assert result.updated_raw_results[0] == enriched_workspace
            assert result.deleted_raw_results == []
            mock_client.get_single_workspace.assert_called_once_with("ws-123")
            mock_enrich.assert_called_once_with(mock_client, workspace_data)

    @pytest.mark.asyncio
    async def test_handle_event_workspace_with_tags(self, processor: Any) -> None:
        payload: dict[str, Any] = {"workspace_id": "ws-456"}
        resource_config = MagicMock()

        workspace_data = {
            "id": "ws-456",
            "attributes": {"name": "workspace-with-tags"},
        }
        enriched_workspace = {
            "id": "ws-456",
            "attributes": {"name": "workspace-with-tags"},
            "__tags": [
                {"id": "tag-1", "attributes": {"name": "env"}},
                {"id": "tag-2", "attributes": {"name": "prod"}},
            ],
        }

        mock_client = MagicMock()
        mock_client.get_single_workspace = AsyncMock(return_value=workspace_data)

        with (
            patch(
                "webhook_processors.workspace_webhook_processor.init_terraform_client"
            ) as mock_init,
            patch(
                "webhook_processors.workspace_webhook_processor.enrich_workspace_with_tags",
                new_callable=AsyncMock,
            ) as mock_enrich,
        ):
            mock_init.return_value = mock_client
            mock_enrich.return_value = enriched_workspace

            result = await processor.handle_event(payload, resource_config)

            assert len(result.updated_raw_results[0]["__tags"]) == 2

    @pytest.mark.asyncio
    async def test_handle_event_workspace_without_tags(self, processor: Any) -> None:
        payload: dict[str, Any] = {"workspace_id": "ws-789"}
        resource_config = MagicMock()

        workspace_data = {
            "id": "ws-789",
            "attributes": {"name": "workspace-no-tags"},
        }
        enriched_workspace = {
            "id": "ws-789",
            "attributes": {"name": "workspace-no-tags"},
            "__tags": [],
        }

        mock_client = MagicMock()
        mock_client.get_single_workspace = AsyncMock(return_value=workspace_data)

        with (
            patch(
                "webhook_processors.workspace_webhook_processor.init_terraform_client"
            ) as mock_init,
            patch(
                "webhook_processors.workspace_webhook_processor.enrich_workspace_with_tags",
                new_callable=AsyncMock,
            ) as mock_enrich,
        ):
            mock_init.return_value = mock_client
            mock_enrich.return_value = enriched_workspace

            result = await processor.handle_event(payload, resource_config)

            assert result.updated_raw_results[0]["__tags"] == []

    @pytest.mark.asyncio
    async def test_handle_event_preserves_workspace_data(self, processor: Any) -> None:
        payload: dict[str, Any] = {
            "workspace_id": "ws-123",
            "extra_field": "should_be_ignored",
        }
        resource_config = MagicMock()

        workspace_data = {
            "id": "ws-123",
            "attributes": {
                "name": "test-workspace",
                "locked": False,
                "terraform-version": "1.5.0",
            },
            "relationships": {
                "organization": {"data": {"id": "org-1"}},
            },
        }
        enriched_workspace = {
            **workspace_data,
            "__tags": [{"id": "tag-1"}],
        }

        mock_client = MagicMock()
        mock_client.get_single_workspace = AsyncMock(return_value=workspace_data)

        with (
            patch(
                "webhook_processors.workspace_webhook_processor.init_terraform_client"
            ) as mock_init,
            patch(
                "webhook_processors.workspace_webhook_processor.enrich_workspace_with_tags",
                new_callable=AsyncMock,
            ) as mock_enrich,
        ):
            mock_init.return_value = mock_client
            mock_enrich.return_value = enriched_workspace

            result = await processor.handle_event(payload, resource_config)

            assert result.updated_raw_results[0]["id"] == "ws-123"
            assert (
                result.updated_raw_results[0]["attributes"]["name"] == "test-workspace"
            )
            assert result.updated_raw_results[0]["attributes"]["locked"] is False
            assert (
                result.updated_raw_results[0]["attributes"]["terraform-version"]
                == "1.5.0"
            )

    @pytest.mark.asyncio
    async def test_handle_event_calls_init_terraform_client(
        self, processor: Any
    ) -> None:
        payload: dict[str, Any] = {"workspace_id": "ws-123"}
        resource_config = MagicMock()

        workspace_data = {"id": "ws-123"}
        enriched_workspace = {"id": "ws-123", "__tags": []}

        mock_client = MagicMock()
        mock_client.get_single_workspace = AsyncMock(return_value=workspace_data)

        with (
            patch(
                "webhook_processors.workspace_webhook_processor.init_terraform_client"
            ) as mock_init,
            patch(
                "webhook_processors.workspace_webhook_processor.enrich_workspace_with_tags",
                new_callable=AsyncMock,
            ) as mock_enrich,
        ):
            mock_init.return_value = mock_client
            mock_enrich.return_value = enriched_workspace

            await processor.handle_event(payload, resource_config)

            mock_init.assert_called_once()
