from unittest.mock import AsyncMock, MagicMock

import pytest

from integration import GithubIntegration
from port_ocean.exceptions.api import EmptyPortAppConfigError


@pytest.fixture
def mock_context() -> MagicMock:
    context = MagicMock()
    context.port_client.get_current_integration = AsyncMock()
    context.integration_config = {"github_organization": "test-org"}
    return context


@pytest.fixture
def app_config_handler(
    mock_context: MagicMock,
) -> GithubIntegration.AppConfigHandlerClass:
    return GithubIntegration.AppConfigHandlerClass(mock_context)


async def test_get_port_app_config_empty_config_returns_empty_dict(
    app_config_handler: GithubIntegration.AppConfigHandlerClass,
    mock_context: MagicMock,
) -> None:
    mock_context.port_client.get_current_integration.return_value = {"config": {}}

    result = await app_config_handler._get_port_app_config()

    assert result == {}
    mock_context.port_client.get_current_integration.assert_awaited_once()


async def test_get_port_app_config_non_empty_config_returns_api_config(
    app_config_handler: GithubIntegration.AppConfigHandlerClass,
    mock_context: MagicMock,
) -> None:
    expected_config = {"resources": [{"kind": "repository", "selector": {}}]}
    mock_context.port_client.get_current_integration.return_value = {
        "config": expected_config
    }

    result = await app_config_handler._get_port_app_config()

    assert result == expected_config
    mock_context.port_client.get_current_integration.assert_awaited_once()


async def test_get_port_app_config_repo_managed_missing_github_org_raises(
    app_config_handler: GithubIntegration.AppConfigHandlerClass,
    mock_context: MagicMock,
) -> None:
    mock_context.port_client.get_current_integration.return_value = {
        "config": {"repoManagedMapping": True}
    }
    mock_context.integration_config = {}

    with pytest.raises(EmptyPortAppConfigError):
        await app_config_handler._get_port_app_config()
