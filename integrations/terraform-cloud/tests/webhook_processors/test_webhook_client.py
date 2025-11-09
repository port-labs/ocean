from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from webhook_processors.webhook_client import TerraformWebhookClient


@pytest.fixture
def webhook_client() -> Any:
    return TerraformWebhookClient(
        terraform_base_url="https://app.terraform.io", auth_token="test-token"
    )


class TestWebhookExists:
    @pytest.mark.asyncio
    async def test_webhook_exists_true(self, webhook_client: Any) -> None:
        response = {
            "data": [
                {
                    "id": "nc-1",
                    "attributes": {"url": "https://example.com/integration/webhook"},
                }
            ]
        }

        with patch.object(
            webhook_client, "send_api_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = response

            result = await webhook_client._webhook_exists(
                "ws-123", "https://example.com/integration/webhook"
            )

            assert result is True
            mock_send.assert_called_once_with(
                endpoint="workspaces/ws-123/notification-configurations"
            )

    @pytest.mark.asyncio
    async def test_webhook_exists_false_no_matching_url(
        self, webhook_client: Any
    ) -> None:
        response = {
            "data": [
                {
                    "id": "nc-1",
                    "attributes": {"url": "https://different.com/webhook"},
                }
            ]
        }

        with patch.object(
            webhook_client, "send_api_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = response

            result = await webhook_client._webhook_exists(
                "ws-123", "https://example.com/integration/webhook"
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_webhook_exists_false_empty_response(
        self, webhook_client: Any
    ) -> None:
        response: dict[str, Any] = {"data": []}

        with patch.object(
            webhook_client, "send_api_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = response

            result = await webhook_client._webhook_exists(
                "ws-123", "https://example.com/integration/webhook"
            )

            assert result is False


class TestEnsureWorkspaceWebhook:
    @pytest.mark.asyncio
    async def test_ensure_workspace_webhook_already_exists(
        self, webhook_client: Any
    ) -> None:
        workspace = {
            "id": "ws-123",
            "attributes": {"name": "test-workspace"},
        }
        webhook_url = "https://example.com/integration/webhook"
        semaphore = MagicMock()
        semaphore.__aenter__ = AsyncMock()
        semaphore.__aexit__ = AsyncMock()

        with (
            patch.object(
                webhook_client, "_webhook_exists", new_callable=AsyncMock
            ) as mock_exists,
            patch.object(
                webhook_client, "_create_webhook", new_callable=AsyncMock
            ) as mock_create,
        ):
            mock_exists.return_value = True

            await webhook_client._ensure_workspace_webhook(
                workspace, webhook_url, semaphore
            )

            mock_exists.assert_called_once_with("ws-123", webhook_url)
            mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_workspace_webhook_creates_new(
        self, webhook_client: Any
    ) -> None:
        workspace = {
            "id": "ws-123",
            "attributes": {"name": "test-workspace"},
        }
        webhook_url = "https://example.com/integration/webhook"
        semaphore = MagicMock()
        semaphore.__aenter__ = AsyncMock()
        semaphore.__aexit__ = AsyncMock()

        with (
            patch.object(
                webhook_client, "_webhook_exists", new_callable=AsyncMock
            ) as mock_exists,
            patch.object(
                webhook_client, "_create_webhook", new_callable=AsyncMock
            ) as mock_create,
        ):
            mock_exists.return_value = False

            await webhook_client._ensure_workspace_webhook(
                workspace, webhook_url, semaphore
            )

            mock_exists.assert_called_once_with("ws-123", webhook_url)
            mock_create.assert_called_once_with("ws-123", "test-workspace", webhook_url)

    @pytest.mark.asyncio
    async def test_ensure_workspace_webhook_handles_error(
        self, webhook_client: Any
    ) -> None:
        workspace = {
            "id": "ws-123",
            "attributes": {"name": "test-workspace"},
        }
        webhook_url = "https://example.com/integration/webhook"
        semaphore = MagicMock()
        semaphore.__aenter__ = AsyncMock()
        semaphore.__aexit__ = AsyncMock()

        with patch.object(
            webhook_client, "_webhook_exists", new_callable=AsyncMock
        ) as mock_exists:
            mock_exists.side_effect = Exception("API Error")

            await webhook_client._ensure_workspace_webhook(
                workspace, webhook_url, semaphore
            )

    @pytest.mark.asyncio
    async def test_ensure_workspace_webhook_without_name(
        self, webhook_client: Any
    ) -> None:
        workspace = {"id": "ws-123", "attributes": {}}
        webhook_url = "https://example.com/integration/webhook"
        semaphore = MagicMock()
        semaphore.__aenter__ = AsyncMock()
        semaphore.__aexit__ = AsyncMock()

        with (
            patch.object(
                webhook_client, "_webhook_exists", new_callable=AsyncMock
            ) as mock_exists,
            patch.object(
                webhook_client, "_create_webhook", new_callable=AsyncMock
            ) as mock_create,
        ):
            mock_exists.return_value = False

            await webhook_client._ensure_workspace_webhook(
                workspace, webhook_url, semaphore
            )

            mock_create.assert_called_once_with("ws-123", "ws-123", webhook_url)


class TestEnsureWorkspaceWebhooks:
    @pytest.mark.asyncio
    async def test_ensure_workspace_webhooks_success(self, webhook_client: Any) -> None:
        workspaces = [
            {"id": "ws-1", "attributes": {"name": "workspace-1"}},
            {"id": "ws-2", "attributes": {"name": "workspace-2"}},
        ]

        with (
            patch.object(webhook_client, "get_paginated_workspaces") as mock_workspaces,
            patch.object(
                webhook_client, "_ensure_workspace_webhook", new_callable=AsyncMock
            ) as mock_ensure,
        ):

            async def workspace_generator() -> Any:
                yield workspaces

            mock_workspaces.return_value = workspace_generator()

            await webhook_client.ensure_workspace_webhooks(
                "https://example.com", max_concurrent=5
            )

            assert mock_ensure.call_count == 2

    @pytest.mark.asyncio
    async def test_ensure_workspace_webhooks_strips_trailing_slash(
        self, webhook_client: Any
    ) -> None:
        workspaces = [{"id": "ws-1", "attributes": {"name": "workspace-1"}}]

        with (
            patch.object(webhook_client, "get_paginated_workspaces") as mock_workspaces,
            patch.object(
                webhook_client, "_ensure_workspace_webhook", new_callable=AsyncMock
            ) as mock_ensure,
        ):

            async def workspace_generator() -> Any:
                yield workspaces

            mock_workspaces.return_value = workspace_generator()

            await webhook_client.ensure_workspace_webhooks("https://example.com/")

            expected_url = "https://example.com/integration/webhook"
            call_args = mock_ensure.call_args[0]
            assert call_args[1] == expected_url

    @pytest.mark.asyncio
    async def test_ensure_workspace_webhooks_multiple_batches(
        self, webhook_client: Any
    ) -> None:
        batch1 = [{"id": "ws-1", "attributes": {"name": "workspace-1"}}]
        batch2 = [{"id": "ws-2", "attributes": {"name": "workspace-2"}}]

        with (
            patch.object(webhook_client, "get_paginated_workspaces") as mock_workspaces,
            patch.object(
                webhook_client, "_ensure_workspace_webhook", new_callable=AsyncMock
            ) as mock_ensure,
        ):

            async def workspace_generator() -> Any:
                yield batch1
                yield batch2

            mock_workspaces.return_value = workspace_generator()

            await webhook_client.ensure_workspace_webhooks("https://example.com")

            assert mock_ensure.call_count == 2


class TestCreateWebhook:
    @pytest.mark.asyncio
    async def test_create_webhook_success(self, webhook_client: Any) -> None:
        with patch.object(
            webhook_client, "send_api_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = {"data": {"id": "nc-123"}}

            await webhook_client._create_webhook(
                "ws-123", "test-workspace", "https://example.com/webhook"
            )

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert (
                call_args.kwargs["endpoint"]
                == "workspaces/ws-123/notification-configurations"
            )
            assert call_args.kwargs["method"] == "POST"
            assert (
                call_args.kwargs["json_data"]["data"]["type"]
                == "notification-configuration"
            )
            assert (
                call_args.kwargs["json_data"]["data"]["attributes"]["url"]
                == "https://example.com/webhook"
            )
            assert (
                call_args.kwargs["json_data"]["data"]["attributes"]["enabled"] is True
            )

    @pytest.mark.asyncio
    async def test_create_webhook_with_correct_triggers(
        self, webhook_client: Any
    ) -> None:
        with patch.object(
            webhook_client, "send_api_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = {"data": {"id": "nc-123"}}

            await webhook_client._create_webhook(
                "ws-123", "test-workspace", "https://example.com/webhook"
            )

            call_args = mock_send.call_args
            triggers = call_args.kwargs["json_data"]["data"]["attributes"]["triggers"]
            assert "run:applying" in triggers
            assert "run:completed" in triggers
            assert "run:created" in triggers

    @pytest.mark.asyncio
    async def test_create_webhook_failure(self, webhook_client: Any) -> None:
        with patch.object(
            webhook_client, "send_api_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.side_effect = Exception("API Error")

            with pytest.raises(Exception, match="API Error"):
                await webhook_client._create_webhook(
                    "ws-123", "test-workspace", "https://example.com/webhook"
                )


class TestListWorkspaceWebhooks:
    @pytest.mark.asyncio
    async def test_list_workspace_webhooks_success(self, webhook_client: Any) -> None:
        webhooks = [
            {"id": "nc-1", "attributes": {"url": "https://example.com/webhook1"}},
            {"id": "nc-2", "attributes": {"url": "https://example.com/webhook2"}},
        ]

        with patch.object(webhook_client, "get_paginated_resources") as mock_paginated:

            async def webhook_generator() -> Any:
                yield webhooks

            mock_paginated.return_value = webhook_generator()

            result = []
            async for batch in webhook_client.list_workspace_webhooks("ws-123"):
                result.extend(batch)

            assert len(result) == 2
            mock_paginated.assert_called_once_with(
                "workspaces/ws-123/notification-configurations"
            )

    @pytest.mark.asyncio
    async def test_list_workspace_webhooks_empty(self, webhook_client: Any) -> None:
        with patch.object(webhook_client, "get_paginated_resources") as mock_paginated:

            async def webhook_generator() -> Any:
                yield []

            mock_paginated.return_value = webhook_generator()

            result = []
            async for batch in webhook_client.list_workspace_webhooks("ws-123"):
                result.extend(batch)

            assert not result
