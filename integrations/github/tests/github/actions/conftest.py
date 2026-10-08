from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from github.clients.http.rest_client import GithubRestClient
from port_ocean.core.models import (
    ActionRun,
    IntegrationActionInvocationPayload,
    RunStatus,
)


def make_action_run(
    action_name: str, execution_properties: dict[str, Any]
) -> ActionRun:
    return ActionRun(
        id="run-123",
        status=RunStatus.IN_PROGRESS,
        action=ActionRun.Action(identifier=action_name),
        payload=IntegrationActionInvocationPayload(
            type="INTEGRATION_ACTION",
            installationId="inst-1",
            integrationActionType=action_name,
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture
def mock_port_client(patched_ocean: MagicMock) -> MagicMock:
    return patched_ocean.port_client


@pytest.fixture
def mock_rest_client() -> MagicMock:
    client = MagicMock(spec=GithubRestClient)
    client.base_url = "https://api.github.com"
    client.send_api_request = AsyncMock()
    client.make_request = AsyncMock()
    client.get_rate_limit_status = MagicMock(return_value=None)
    return client
