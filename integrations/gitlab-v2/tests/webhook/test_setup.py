import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from gitlab.webhook.setup import (
    setup_webhooks,
    _setup_single_namespace_webhooks,
    _setup_multi_group_webhooks,
)


@pytest.fixture
def mock_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_webhook_factories():
    """Patch both webhook factory classes."""
    with (
        patch("gitlab.webhook.setup.GroupWebHook") as group_cls,
        patch("gitlab.webhook.setup.ProjectWebHook") as project_cls,
    ):
        group_cls.return_value.create_webhooks_for_all_groups = AsyncMock()
        group_cls.return_value.create_group_webhook = AsyncMock()
        project_cls.return_value.create_webhooks_for_personal_projects = AsyncMock()
        yield {"group": group_cls, "project": project_cls}


@pytest.mark.asyncio
class TestSetupWebhooks:
    async def test_skips_when_webhooks_not_supported(self) -> None:
        with patch("gitlab.webhook.setup.create_gitlab_client") as mock_create:
            await setup_webhooks(
                should_process_webhooks=False,
                base_url="https://app.example.com",
                gitlab_group=None,
            )
            mock_create.assert_not_called()

    async def test_skips_when_no_base_url(self) -> None:
        with patch("gitlab.webhook.setup.create_gitlab_client") as mock_create:
            await setup_webhooks(
                should_process_webhooks=True,
                base_url=None,
                gitlab_group=None,
            )
            mock_create.assert_not_called()

    async def test_delegates_to_single_namespace(self, mock_client: MagicMock) -> None:
        with patch(
            "gitlab.webhook.setup._setup_single_namespace_webhooks",
            new_callable=AsyncMock,
        ) as mock_single:
            await setup_webhooks(
                should_process_webhooks=True,
                base_url="https://app.example.com",
                gitlab_group="my-group",
                client=mock_client,
            )

            mock_single.assert_awaited_once_with(
                mock_client, "https://app.example.com", "my-group"
            )

    async def test_delegates_to_multi_group(self, mock_client: MagicMock) -> None:
        with patch(
            "gitlab.webhook.setup._setup_multi_group_webhooks",
            new_callable=AsyncMock,
        ) as mock_multi:
            await setup_webhooks(
                should_process_webhooks=True,
                base_url="https://app.example.com",
                gitlab_group=None,
                client=mock_client,
                include_authenticated_user=True,
            )

            mock_multi.assert_awaited_once_with(
                mock_client, "https://app.example.com", True
            )


@pytest.mark.asyncio
class TestSetupSingleNamespaceWebhooks:
    async def test_routes_to_group_webhook(
        self, mock_client: MagicMock, mock_webhook_factories
    ) -> None:
        mock_client.is_personal_namespace = AsyncMock(return_value=False)
        mock_client.get_group = AsyncMock(return_value={"id": 42})

        await _setup_single_namespace_webhooks(
            mock_client, "https://app.example.com", "my-group"
        )

        mock_client.is_personal_namespace.assert_awaited_once_with("my-group")
        mock_client.get_group.assert_awaited_once_with("my-group")
        mock_webhook_factories[
            "group"
        ].return_value.create_group_webhook.assert_awaited_once_with(42)
        mock_webhook_factories["project"].assert_not_called()

    async def test_routes_to_project_webhooks(
        self, mock_client: MagicMock, mock_webhook_factories
    ) -> None:
        mock_client.is_personal_namespace = AsyncMock(return_value=True)

        await _setup_single_namespace_webhooks(
            mock_client, "https://app.example.com", "alice"
        )

        mock_client.is_personal_namespace.assert_awaited_once_with("alice")
        mock_client.get_group.assert_not_called()
        mock_webhook_factories[
            "project"
        ].return_value.create_webhooks_for_personal_projects.assert_awaited_once()
        mock_webhook_factories["group"].assert_not_called()


@pytest.mark.asyncio
class TestSetupMultiGroupWebhooks:
    async def test_with_personal_namespace(
        self, mock_client: MagicMock, mock_webhook_factories
    ) -> None:
        await _setup_multi_group_webhooks(
            mock_client, "https://app.example.com", include_authenticated_user=True
        )

        factories = mock_webhook_factories
        factories[
            "group"
        ].return_value.create_webhooks_for_all_groups.assert_awaited_once()
        factories[
            "project"
        ].return_value.create_webhooks_for_personal_projects.assert_awaited_once()

    async def test_without_personal_namespace(
        self, mock_client: MagicMock, mock_webhook_factories
    ) -> None:
        await _setup_multi_group_webhooks(
            mock_client, "https://app.example.com", include_authenticated_user=False
        )

        factories = mock_webhook_factories
        factories[
            "group"
        ].return_value.create_webhooks_for_all_groups.assert_awaited_once()
        factories[
            "project"
        ].return_value.create_webhooks_for_personal_projects.assert_not_awaited()
