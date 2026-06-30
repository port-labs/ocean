import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from gitlab.webhook.webhook_factory.client_factory import GitlabWebhookFactory


@pytest.mark.asyncio
class TestGitlabWebhookFactory:
    async def test_routes_to_group_webhook_for_group_namespace(self) -> None:
        client = MagicMock()
        client.is_personal_namespace = AsyncMock(return_value=False)
        client.get_group = AsyncMock(return_value={"id": 42})

        with (
            patch(
                "gitlab.webhook.webhook_factory.client_factory.GroupWebHook"
            ) as group_webhook_cls,
            patch(
                "gitlab.webhook.webhook_factory.client_factory.ProjectWebHook"
            ) as project_webhook_cls,
        ):
            group_webhook = group_webhook_cls.return_value
            group_webhook.create_group_webhook = AsyncMock()

            await GitlabWebhookFactory.create_webhooks_for_namespace(
                client, "https://app.example.com", "my-group"
            )

            client.is_personal_namespace.assert_awaited_once_with("my-group")
            client.get_group.assert_awaited_once_with("my-group")
            group_webhook.create_group_webhook.assert_awaited_once_with(42)
            project_webhook_cls.assert_not_called()

    async def test_routes_to_project_webhooks_for_personal_namespace(self) -> None:
        client = MagicMock()
        client.is_personal_namespace = AsyncMock(return_value=True)

        with (
            patch(
                "gitlab.webhook.webhook_factory.client_factory.GroupWebHook"
            ) as group_webhook_cls,
            patch(
                "gitlab.webhook.webhook_factory.client_factory.ProjectWebHook"
            ) as project_webhook_cls,
        ):
            project_webhook = project_webhook_cls.return_value
            project_webhook.create_webhooks_for_personal_projects = AsyncMock()

            await GitlabWebhookFactory.create_webhooks_for_namespace(
                client, "https://app.example.com", "alice"
            )

            client.is_personal_namespace.assert_awaited_once_with("alice")
            client.get_group.assert_not_called()
            project_webhook.create_webhooks_for_personal_projects.assert_awaited_once()
            group_webhook_cls.assert_not_called()
