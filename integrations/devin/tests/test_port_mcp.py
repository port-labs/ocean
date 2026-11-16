import asyncio
from typing import Any
from unittest.mock import patch

import pytest
from port_ocean.core.models import ResolvedExecutionIdentity
from port_ocean.exceptions.execution_manager import ActionExecutionError

from actions.create_session_executor import CreateSessionExecutor
from actions.port_mcp_utils import (
    DEFAULT_PORT_MCP_ORG_SECRET_KEY,
    merge_port_mcp_secret_id,
    port_mcp_secret_key_from_config,
    rotate_port_mcp_org_secret,
    validate_port_mcp_secret_key,
)
from tests.fakes import FakeDevin, FakePort, make_node_run, patched_ocean
from tests.test_actions import build


class FakeDevinSecretsClient:
    org_id = "org-1"

    def __init__(self) -> None:
        self.secrets: dict[str, dict[str, Any]] = {}
        self._counter = 0
        self.delete_calls: list[str] = []
        self.create_calls: list[tuple[str, str]] = []
        self._in_critical = 0
        self.max_in_critical = 0

    async def find_secret_id_by_key(self, key: str) -> str | None:
        for secret_id, item in self.secrets.items():
            if item.get("key") == key:
                return secret_id
        return None

    async def delete_secret(self, secret_id: str) -> None:
        self.delete_calls.append(secret_id)
        self._in_critical += 1
        self.max_in_critical = max(self.max_in_critical, self._in_critical)
        await asyncio.sleep(0.05)
        self._in_critical -= 1
        self.secrets.pop(secret_id, None)

    async def create_secret(
        self,
        key: str,
        value: str,
        *,
        secret_type: str = "key-value",
        is_sensitive: bool = True,
    ) -> dict[str, Any]:
        self.create_calls.append((key, value))
        self._counter += 1
        secret_id = f"sec-{self._counter}"
        self.secrets[secret_id] = {
            "secret_id": secret_id,
            "key": key,
            "value": value,
            "type": secret_type,
            "is_sensitive": is_sensitive,
        }
        return {"secret_id": secret_id, "key": key}


@pytest.fixture
def devin() -> FakeDevin:
    return FakeDevin()


@pytest.fixture
def port() -> FakePort:
    return FakePort()


async def test_rotate_port_mcp_org_secret_requires_token() -> None:
    run = make_node_run("wfnr_1", "create_session", {"prompt": "hi", "enablePortMcp": True})
    client = FakeDevinSecretsClient()
    with pytest.raises(ActionExecutionError, match="enablePortMcp requires"):
        await rotate_port_mcp_org_secret(client, run, True)


async def test_rotate_creates_then_replaces_secret() -> None:
    run = make_node_run(
        "wfnr_2",
        "create_session",
        {"prompt": "hi", "enablePortMcp": True},
    )
    run.execution_identity = ResolvedExecutionIdentity(
        type="actor", identifier="user@example.com"
    )
    client = FakeDevinSecretsClient()
    client.secrets["sec-old"] = {
        "secret_id": "sec-old",
        "key": DEFAULT_PORT_MCP_ORG_SECRET_KEY,
        "value": "stale",
    }

    with patch("actions.port_mcp_utils.get_run_access_token", return_value="port.jwt"):
        first = await rotate_port_mcp_org_secret(client, run, True)
        second = await rotate_port_mcp_org_secret(client, run, True)

    assert first == "sec-1"
    assert second == "sec-2"
    assert client.delete_calls == ["sec-old", "sec-1"]
    assert client.create_calls == [
        (DEFAULT_PORT_MCP_ORG_SECRET_KEY, "port.jwt"),
        (DEFAULT_PORT_MCP_ORG_SECRET_KEY, "port.jwt"),
    ]
    assert set(client.secrets) == {"sec-2"}


def test_merge_port_mcp_secret_id_dedupes_user_ids() -> None:
    body: dict[str, Any] = {"secret_ids": ["user-secret", "sec-1"]}
    merge_port_mcp_secret_id(body, "sec-1")
    assert body["secret_ids"] == ["user-secret", "sec-1"]


async def test_rotate_lock_serializes_concurrent_org_access() -> None:
    run = make_node_run(
        "wfnr_3",
        "create_session",
        {"prompt": "hi", "enablePortMcp": True},
    )
    run.execution_identity = ResolvedExecutionIdentity(
        type="actor", identifier="user@example.com"
    )
    client = FakeDevinSecretsClient()
    client.secrets["sec-old"] = {
        "secret_id": "sec-old",
        "key": DEFAULT_PORT_MCP_ORG_SECRET_KEY,
        "value": "stale",
    }
    started = asyncio.Event()

    async def delete_when_first_enters(secret_id: str) -> None:
        if not started.is_set():
            started.set()
        await FakeDevinSecretsClient.delete_secret(client, secret_id)

    client.delete_secret = delete_when_first_enters  # type: ignore[method-assign]

    with patch("actions.port_mcp_utils.get_run_access_token", return_value="port.jwt"):
        first = asyncio.create_task(rotate_port_mcp_org_secret(client, run, True))
        await started.wait()
        second = asyncio.create_task(rotate_port_mcp_org_secret(client, run, True))
        await asyncio.gather(first, second)

    assert client.max_in_critical == 1


def test_port_mcp_secret_key_must_start_with_mcp() -> None:
    with pytest.raises(ValueError, match="MCP_"):
        validate_port_mcp_secret_key("PORT_TOKEN")

    with pytest.raises(ActionExecutionError, match="MCP_"):
        port_mcp_secret_key_from_config({"port_mcp_secret_key": "BAD"})


def test_port_mcp_secret_key_from_config_defaults() -> None:
    assert port_mcp_secret_key_from_config({}) == DEFAULT_PORT_MCP_ORG_SECRET_KEY
    assert (
        port_mcp_secret_key_from_config({"port_mcp_secret_key": "MCP_CUSTOM"})
        == "MCP_CUSTOM"
    )


async def test_rotate_uses_custom_secret_key() -> None:
    run = make_node_run(
        "wfnr_5",
        "create_session",
        {"prompt": "hi", "enablePortMcp": True},
    )
    run.execution_identity = ResolvedExecutionIdentity(
        type="actor", identifier="user@example.com"
    )
    client = FakeDevinSecretsClient()
    custom = "MCP_CUSTOM_PORT"

    with patch("actions.port_mcp_utils.get_run_access_token", return_value="port.jwt"):
        secret_id = await rotate_port_mcp_org_secret(
            client, run, True, secret_key=custom
        )

    assert secret_id == "sec-1"
    assert client.create_calls == [(custom, "port.jwt")]
    assert client.secrets["sec-1"]["key"] == custom


async def test_create_session_merges_rotated_secret_id(
    devin: FakeDevin, port: FakePort
) -> None:
    run = make_node_run(
        "wfnr_4",
        "create_session",
        {
            "prompt": "Use Port MCP",
            "enablePortMcp": True,
            "secretIds": ["user-secret"],
        },
    )
    run.execution_identity = ResolvedExecutionIdentity(
        type="actor", identifier="user@example.com"
    )
    client = FakeDevinSecretsClient()
    executor = build(CreateSessionExecutor, devin)
    executor.sessions.client = client

    with patched_ocean(port) as ocean_mock:
        ocean_mock.config.port.mcp_url = "https://mcp.port.io/v1"
        ocean_mock.integration_config = {"port_mcp_secret_key": "MCP_PORT_TOKEN"}
        with patch(
            "actions.port_mcp_utils.get_run_access_token", return_value="port.jwt"
        ):
            await executor.execute(run)

    assert devin.last_create_body.get("session_secrets") is None
    assert devin.last_create_body["secret_ids"] == ["user-secret", "sec-1"]