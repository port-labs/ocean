import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from gitlab.webhook.setup import setup_webhooks


@pytest.mark.asyncio
class TestSetupWebhooks:
    async def test_skips_when_webhooks_not_supported(self) -> None:
        with patch("gitlab.webhook.setup.create_gitlab_client") as mock_create_client:
            await setup_webhooks(
                should_process_webhooks=False,
                base_url="https://app.example.com",
                gitlab_group=None,
            )

            mock_create_client.assert_not_called()

    async def test_single_namespace_mode(self) -> None:
        client = MagicMock()
        with (
            patch(
                "gitlab.webhook.setup.GitlabWebhookFactory.create_webhooks_for_namespace",
                new_callable=AsyncMock,
            ) as mock_create_namespace,
            patch("gitlab.webhook.setup.GroupWebHook") as group_webhook_cls,
            patch("gitlab.webhook.setup.ProjectWebHook") as project_webhook_cls,
        ):
            await setup_webhooks(
                should_process_webhooks=True,
                base_url="https://app.example.com",
                gitlab_group="my-group",
                client=client,
            )

            mock_create_namespace.assert_awaited_once_with(
                client, "https://app.example.com", "my-group"
            )
            group_webhook_cls.assert_not_called()
            project_webhook_cls.assert_not_called()

    async def test_multi_group_mode_with_personal_namespace(self) -> None:
        client = MagicMock()
        with (
            patch(
                "gitlab.webhook.setup.GitlabWebhookFactory.create_webhooks_for_namespace",
                new_callable=AsyncMock,
            ) as mock_create_namespace,
            patch("gitlab.webhook.setup.GroupWebHook") as group_webhook_cls,
            patch("gitlab.webhook.setup.ProjectWebHook") as project_webhook_cls,
        ):
            group_webhook = group_webhook_cls.return_value
            group_webhook.create_webhooks_for_all_groups = AsyncMock()
            project_webhook = project_webhook_cls.return_value
            project_webhook.create_webhooks_for_personal_projects = AsyncMock()

            await setup_webhooks(
                should_process_webhooks=True,
                base_url="https://app.example.com",
                gitlab_group=None,
                client=client,
                include_authenticated_user=True,
            )

            mock_create_namespace.assert_not_awaited()
            group_webhook.create_webhooks_for_all_groups.assert_awaited_once()
            project_webhook.create_webhooks_for_personal_projects.assert_awaited_once()

    async def test_multi_group_mode_without_personal_namespace(self) -> None:
        client = MagicMock()
        with (
            patch("gitlab.webhook.setup.GroupWebHook") as group_webhook_cls,
            patch("gitlab.webhook.setup.ProjectWebHook") as project_webhook_cls,
        ):
            group_webhook = group_webhook_cls.return_value
            group_webhook.create_webhooks_for_all_groups = AsyncMock()
            project_webhook = project_webhook_cls.return_value
            project_webhook.create_webhooks_for_personal_projects = AsyncMock()

            await setup_webhooks(
                should_process_webhooks=True,
                base_url="https://app.example.com",
                gitlab_group=None,
                client=client,
                include_authenticated_user=False,
            )

            group_webhook.create_webhooks_for_all_groups.assert_awaited_once()
            project_webhook.create_webhooks_for_personal_projects.assert_not_awaited()
