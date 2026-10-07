from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.core.models import (
    IntegrationRun,
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from gitlab.actions.abstract_gitlab_executor import AbstractGitlabExecutor
from gitlab.clients.gitlab_client import GitLabClient


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_app = MagicMock()
        mock_app.config.client_timeout = 60
        mock_app.config.integration.config = {
            "gitlab_host": "https://gitlab.example.com",
            "gitlab_token": "integration-token",
        }
        mock_app.cache_provider = AsyncMock()
        mock_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        pass


class _StubExecutor(AbstractGitlabExecutor):
    async def execute(self, run: IntegrationRun) -> None:
        return None


def _make_run() -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run-1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationProvider="gitlab",
            integrationInvocationType="create_merge_request",
            integrationActionExecutionProperties={},
        ),
    )


@pytest.mark.asyncio
async def test_api_client_for_run_disables_token_refresh_for_user_token() -> None:
    with patch(
        "gitlab.actions.abstract_gitlab_executor.create_gitlab_client"
    ) as mock_create:
        mock_create.return_value = MagicMock()
        executor = _StubExecutor()

    with (
        patch(
            "gitlab.actions.abstract_gitlab_executor.resolve_user_token",
            AsyncMock(return_value="user-oauth-token"),
        ),
        patch("gitlab.actions.abstract_gitlab_executor.ocean") as mock_ocean,
    ):
        mock_ocean.integration_config = {"gitlab_host": "https://gitlab.example.com/"}

        async with executor._api_client_for_run(_make_run()) as api_client:
            assert isinstance(api_client, GitLabClient)
            assert api_client.rest.token == "user-oauth-token"
            assert api_client.rest._auth_client._allow_token_refresh is False


@pytest.mark.asyncio
async def test_api_client_for_run_reuses_integration_client_without_user_token() -> (
    None
):
    with patch(
        "gitlab.actions.abstract_gitlab_executor.create_gitlab_client"
    ) as mock_create:
        integration_client = MagicMock()
        mock_create.return_value = integration_client
        executor = _StubExecutor()

    with (
        patch(
            "gitlab.actions.abstract_gitlab_executor.resolve_user_token",
            AsyncMock(return_value=None),
        ),
        patch(
            "gitlab.actions.abstract_gitlab_executor.GitLabClient"
        ) as mock_gitlab_client,
    ):
        async with executor._api_client_for_run(_make_run()) as api_client:
            assert api_client is integration_client

        mock_gitlab_client.assert_not_called()
