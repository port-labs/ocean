from unittest.mock import patch

import pytest
from port_ocean.core.models import ResolvedExecutionIdentity
from port_ocean.exceptions.execution_manager import ActionExecutionError

from actions.create_session_executor import CreateSessionExecutor
from actions.port_mcp_utils import (
    DEFAULT_PORT_MCP_SESSION_SECRET_KEY,
    apply_port_mcp_session_secrets,
    port_mcp_secret_key_from_config,
    validate_port_mcp_secret_key,
)
from tests.fakes import FakeDevin, FakePort, make_node_run, patched_ocean
from tests.test_actions import build


@pytest.fixture
def devin() -> FakeDevin:
    return FakeDevin()


@pytest.fixture
def port() -> FakePort:
    return FakePort()


def test_apply_port_mcp_session_secrets_requires_token() -> None:
    run = make_node_run("wfnr_1", "create_session", {"prompt": "hi", "enablePortMcp": True})
    with pytest.raises(ActionExecutionError, match="enablePortMcp requires"):
        apply_port_mcp_session_secrets(
            {}, run, True, DEFAULT_PORT_MCP_SESSION_SECRET_KEY
        )


def test_apply_port_mcp_session_secrets_uses_configured_key() -> None:
    run = make_node_run("wfnr_2", "create_session", {"prompt": "hi"})
    run.execution_identity = ResolvedExecutionIdentity(
        type="actor", identifier="user@example.com"
    )
    body: dict = {}
    with patch("actions.port_mcp_utils.get_run_access_token", return_value="port.jwt"):
        apply_port_mcp_session_secrets(body, run, True, "MCP_CUSTOM")

    assert body["session_secrets"] == [
        {"key": "MCP_CUSTOM", "value": "port.jwt", "sensitive": True}
    ]


def test_port_mcp_secret_key_from_config() -> None:
    assert port_mcp_secret_key_from_config({}) == DEFAULT_PORT_MCP_SESSION_SECRET_KEY
    assert (
        port_mcp_secret_key_from_config({"port_mcp_secret_key": "MCP_MY_PORT"})
        == "MCP_MY_PORT"
    )
    with pytest.raises(ValueError, match="MCP_"):
        validate_port_mcp_secret_key("PORT_TOKEN")
    with pytest.raises(ActionExecutionError, match="MCP_"):
        port_mcp_secret_key_from_config({"port_mcp_secret_key": "BAD"})


async def test_create_session_injects_session_secret(
    devin: FakeDevin, port: FakePort
) -> None:
    run = make_node_run(
        "wfnr_3",
        "create_session",
        {"prompt": "Use Port MCP", "enablePortMcp": True},
    )
    run.execution_identity = ResolvedExecutionIdentity(
        type="actor", identifier="user@example.com"
    )
    with patched_ocean(port) as ocean_mock:
        ocean_mock.config.port.mcp_url = "https://mcp.port.io/v1"
        ocean_mock.integration_config = {"port_mcp_secret_key": "MCP_PORT_TOKEN"}
        with patch(
            "actions.port_mcp_utils.get_run_access_token", return_value="port.jwt"
        ):
            await build(CreateSessionExecutor, devin).execute(run)

    secrets = devin.last_create_body.get("session_secrets") or []
    assert secrets == [
        {
            "key": DEFAULT_PORT_MCP_SESSION_SECRET_KEY,
            "value": "port.jwt",
            "sensitive": True,
        }
    ]