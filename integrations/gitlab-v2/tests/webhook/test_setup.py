from typing import Generator

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
def mock_group_webhook() -> Generator[MagicMock, None, None]:
    with patch("gitlab.webhook.setup.GroupWebHook") as cls:
        cls.return_value.create_webhooks_for_all_groups = AsyncMock()
        cls.return_value.create_group_webhook = AsyncMock()
        yield cls


@pytest.fixture
def mock_project_webhook() -> Generator[MagicMock, None, None]:
    with patch("gitlab.webhook.setup.ProjectWebHook") as cls:
        cls.return_value.create_webhooks_for_personal_projects = AsyncMock()
        yield cls


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
            )

            mock_multi.assert_awaited_once_with(mock_client, "https://app.example.com")


@pytest.mark.asyncio
class TestSetupSingleNamespaceWebhooks:
    async def test_routes_to_group_webhook(
        self,
        mock_client: MagicMock,
        mock_group_webhook: MagicMock,
        mock_project_webhook: MagicMock,
    ) -> None:
        mock_client.get_group_if_exists = AsyncMock(return_value={"id": 42})

        await _setup_single_namespace_webhooks(
            mock_client, "https://app.example.com", "my-group"
        )

        mock_client.get_group_if_exists.assert_awaited_once_with("my-group")
        mock_group_webhook.return_value.create_group_webhook.assert_awaited_once_with(
            42
        )
        mock_project_webhook.return_value.create_webhooks_for_personal_projects.assert_not_awaited()

    async def test_routes_to_project_webhooks_for_personal(
        self,
        mock_client: MagicMock,
        mock_group_webhook: MagicMock,
        mock_project_webhook: MagicMock,
    ) -> None:
        mock_client.get_group_if_exists = AsyncMock(return_value=None)

        await _setup_single_namespace_webhooks(
            mock_client, "https://app.example.com", "alice"
        )

        mock_client.get_group_if_exists.assert_awaited_once_with("alice")
        mock_project_webhook.return_value.create_webhooks_for_personal_projects.assert_awaited_once()
        mock_group_webhook.return_value.create_group_webhook.assert_not_awaited()


@pytest.mark.asyncio
class TestSetupMultiGroupWebhooks:
    async def test_with_personal_namespace_enabled(
        self,
        mock_client: MagicMock,
        mock_group_webhook: MagicMock,
        mock_project_webhook: MagicMock,
    ) -> None:
        mock_config = MagicMock()
        mock_config.include_authenticated_user = True

        with patch("gitlab.webhook.setup.ocean") as mock_ocean:
            mock_ocean.integration.port_app_config_handler.get_port_app_config = (
                AsyncMock()
            )
            # Patch at module level to replace the LocalProxy before it's accessed
            import gitlab.webhook.setup as setup_module

            original_event = setup_module.event  # type: ignore[attr-defined]
            mock_event = MagicMock()
            mock_event.port_app_config = mock_config
            setup_module.event = mock_event  # type: ignore[attr-defined]

            try:
                await _setup_multi_group_webhooks(
                    mock_client, "https://app.example.com"
                )
            finally:
                setup_module.event = original_event  # type: ignore[attr-defined]

        mock_group_webhook.return_value.create_webhooks_for_all_groups.assert_awaited_once()
        mock_project_webhook.return_value.create_webhooks_for_personal_projects.assert_awaited_once()

    async def test_with_personal_namespace_disabled(
        self,
        mock_client: MagicMock,
        mock_group_webhook: MagicMock,
        mock_project_webhook: MagicMock,
    ) -> None:
        mock_config = MagicMock()
        mock_config.include_authenticated_user = False

        with patch("gitlab.webhook.setup.ocean") as mock_ocean:
            mock_ocean.integration.port_app_config_handler.get_port_app_config = (
                AsyncMock()
            )
            import gitlab.webhook.setup as setup_module

            original_event = setup_module.event  # type: ignore[attr-defined]
            mock_event = MagicMock()
            mock_event.port_app_config = mock_config
            setup_module.event = mock_event  # type: ignore[attr-defined]

            try:
                await _setup_multi_group_webhooks(
                    mock_client, "https://app.example.com"
                )
            finally:
                setup_module.event = original_event  # type: ignore[attr-defined]

        mock_group_webhook.return_value.create_webhooks_for_all_groups.assert_awaited_once()
        mock_project_webhook.return_value.create_webhooks_for_personal_projects.assert_not_awaited()
