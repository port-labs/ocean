from unittest.mock import patch

import pytest
from port_ocean.core.models import ResolvedExecutionIdentity
from port_ocean.exceptions.execution_manager import ActionExecutionError

from actions.create_session_executor import CreateSessionExecutor
from actions.port_mcp_utils import PORT_MCP_SESSION_SECRET_KEY, port_mcp_session_secrets
from tests.fakes import FakeDevin, FakePort, build, make_node_run, patched_ocean


@pytest.fixture
def devin() -> FakeDevin:
    return FakeDevin()


@pytest.fixture
def port() -> FakePort:
    return FakePort()


def test_port_mcp_session_secrets_requires_token() -> None:
    run = make_node_run("wfnr_1", "create_session", {"prompt": "hi", "enablePortMcp": True})
    with pytest.raises(ActionExecutionError, match="enablePortMcp requires"):
        port_mcp_session_secrets(run)


async def test_create_session_injects_session_secret(
    devin: FakeDevin, port: FakePort
) -> None:
    run = make_node_run(
        "wfnr_2",
        "create_session",
        {"prompt": "Use Port MCP", "enablePortMcp": True},
    )
    run.execution_identity = ResolvedExecutionIdentity(
        type="actor", identifier="user@example.com"
    )
    with patched_ocean(port) as ocean_mock:
        ocean_mock.config.port.mcp_url = "https://mcp.port.io/v1"
        with patch(
            "actions.port_mcp_utils.get_run_access_token", return_value="port.jwt"
        ):
            await build(CreateSessionExecutor, devin).execute(run)

    secrets = devin.last_create_body.get("session_secrets") or []
    assert secrets == [
        {"key": PORT_MCP_SESSION_SECRET_KEY, "value": "port.jwt", "sensitive": True}
    ]