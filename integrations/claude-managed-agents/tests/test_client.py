from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import anthropic
import httpx
import pytest
from anthropic.types.beta.sessions.beta_managed_agents_text_block import (
    BetaManagedAgentsTextBlock,
)
from anthropic.types.beta.sessions.beta_managed_agents_user_message_event import (
    BetaManagedAgentsUserMessageEvent,
)

from clients.anthropic_client import AnthropicClient, CreateRateLimitInfo, _serialize


class _Model:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def to_dict(self, **kwargs: Any) -> dict[str, Any]:
        return self._data


async def _aiter(items: list[Any]) -> AsyncGenerator[Any, None]:
    for item in items:
        yield item


_RATE_LIMIT_HEADERS = {
    "anthropic-ratelimit-requests-limit": "300",
    "anthropic-ratelimit-requests-remaining": "299",
    "anthropic-ratelimit-requests-reset": "2026-06-15T09:00:00Z",
}


def _raw_response(parsed: Any, headers: dict[str, str] | None = None) -> MagicMock:
    """Build a mock ``with_raw_response`` result: ``.parse()`` and ``.headers``."""
    raw = MagicMock()
    raw.parse.return_value = parsed
    raw.headers = httpx.Headers(headers if headers is not None else _RATE_LIMIT_HEADERS)
    return raw


def _api_status_error(headers: dict[str, str]) -> anthropic.APIStatusError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/agents")
    response = httpx.Response(429, headers=headers, request=request)
    return anthropic.APIStatusError("rate limited", response=response, body=None)


@pytest.fixture
def client() -> AnthropicClient:
    instance = AnthropicClient(
        api_host="https://api.anthropic.com",
        api_key="test-api-key",
        webhook_signing_secret="whsec_test",
        page_size=2,
    )
    instance._client = MagicMock()
    return instance


def test_serialize_prefers_to_dict() -> None:
    assert _serialize(_Model({"id": "x"})) == {"id": "x"}


def test_serialize_plain_dict() -> None:
    assert _serialize({"id": "y"}) == {"id": "y"}


@pytest.mark.asyncio
async def test_get_agents_batches_results(client: AnthropicClient) -> None:
    inner: Any = client._client
    items = [_Model({"id": "a1"}), _Model({"id": "a2"}), _Model({"id": "a3"})]
    inner.beta.agents.list = AsyncMock(return_value=_aiter(items))

    batches = [batch async for batch in client.get_agents()]

    assert batches == [[{"id": "a1"}, {"id": "a2"}], [{"id": "a3"}]]
    inner.beta.agents.list.assert_called_once_with(include_archived=False)


@pytest.mark.asyncio
async def test_get_agents_forwards_include_archived(client: AnthropicClient) -> None:
    inner: Any = client._client
    inner.beta.agents.list = AsyncMock(return_value=_aiter([]))

    [batch async for batch in client.get_agents(include_archived=True)]

    inner.beta.agents.list.assert_called_once_with(include_archived=True)


@pytest.mark.asyncio
async def test_create_agent_builds_payload_and_drops_none(
    client: AnthropicClient,
) -> None:
    inner: Any = client._client
    inner.beta.agents.with_raw_response.create = AsyncMock(
        return_value=_raw_response(_Model({"id": "agent_1"}))
    )

    result = await client.create_agent(
        name="my-agent",
        model="claude-opus-4-6",
        system="be helpful",
        extra={"description": "demo", "metadata": None},
    )

    assert result == {"id": "agent_1"}
    inner.beta.agents.with_raw_response.create.assert_awaited_once_with(
        name="my-agent",
        model="claude-opus-4-6",
        system="be helpful",
        description="demo",
    )


@pytest.mark.asyncio
async def test_create_session_builds_payload(client: AnthropicClient) -> None:
    inner: Any = client._client
    inner.beta.sessions.with_raw_response.create = AsyncMock(
        return_value=_raw_response(_Model({"id": "sess_1"}))
    )

    result = await client.create_session("agent_1", "env_1")

    assert result == {"id": "sess_1"}
    inner.beta.sessions.with_raw_response.create.assert_awaited_once_with(
        agent="agent_1", environment_id="env_1"
    )


@pytest.mark.asyncio
async def test_create_session_forwards_extra(client: AnthropicClient) -> None:
    inner: Any = client._client
    inner.beta.sessions.with_raw_response.create = AsyncMock(
        return_value=_raw_response(_Model({"id": "sess_1"}))
    )

    await client.create_session(
        "agent_1",
        "env_1",
        extra={
            "title": "Demo",
            "metadata": {"owner": "port"},
            "vault_ids": ["vault_1"],
            "resources": [{"type": "memory_store", "memory_store_id": "ms_1"}],
        },
    )

    inner.beta.sessions.with_raw_response.create.assert_awaited_once_with(
        agent="agent_1",
        environment_id="env_1",
        title="Demo",
        metadata={"owner": "port"},
        vault_ids=["vault_1"],
        resources=[{"type": "memory_store", "memory_store_id": "ms_1"}],
    )


@pytest.mark.asyncio
async def test_send_user_message_event_shape(client: AnthropicClient) -> None:
    # send_user_message never sees Managed Agents rate-limit headers (the agent
    # turn runs asynchronously), but with_raw_response is still used to capture
    # the anthropic-workspace-id header for building session console links.
    inner: Any = client._client
    sent_event = BetaManagedAgentsUserMessageEvent(
        id="evt_1",
        type="user.message",
        content=[BetaManagedAgentsTextBlock(type="text", text="hello there")],
    )
    inner.beta.sessions.events.with_raw_response.send = AsyncMock(
        return_value=_raw_response(
            MagicMock(data=[sent_event]), headers={"anthropic-workspace-id": "ws_1"}
        )
    )

    result = await client.send_user_message("sess_1", "hello there")

    assert result.id == "evt_1"
    inner.beta.sessions.events.with_raw_response.send.assert_awaited_once_with(
        "sess_1",
        events=[
            {
                "type": "user.message",
                "content": [{"type": "text", "text": "hello there"}],
            }
        ],
    )


@pytest.mark.asyncio
async def test_send_user_message_does_not_touch_rate_limit_cache(
    client: AnthropicClient,
) -> None:
    inner: Any = client._client
    sent_event = BetaManagedAgentsUserMessageEvent(
        id="evt_1",
        type="user.message",
        content=[BetaManagedAgentsTextBlock(type="text", text="hello there")],
    )
    inner.beta.sessions.events.with_raw_response.send = AsyncMock(
        return_value=_raw_response(
            MagicMock(data=[sent_event]), headers={"anthropic-workspace-id": "ws_1"}
        )
    )

    await client.send_user_message("sess_1", "hello there")

    assert client.get_create_rate_limit_status() is None


@pytest.mark.asyncio
async def test_send_user_message_captures_workspace_id(
    client: AnthropicClient,
) -> None:
    inner: Any = client._client
    sent_event = BetaManagedAgentsUserMessageEvent(
        id="evt_1",
        type="user.message",
        content=[BetaManagedAgentsTextBlock(type="text", text="hello there")],
    )
    inner.beta.sessions.events.with_raw_response.send = AsyncMock(
        return_value=_raw_response(
            MagicMock(data=[sent_event]), headers={"anthropic-workspace-id": "ws_1"}
        )
    )

    await client.send_user_message("sess_1", "hello there")

    assert client.get_workspace_id() == "ws_1"


@pytest.mark.asyncio
async def test_send_user_message_missing_workspace_id_leaves_cache_none(
    client: AnthropicClient,
) -> None:
    inner: Any = client._client
    sent_event = BetaManagedAgentsUserMessageEvent(
        id="evt_1",
        type="user.message",
        content=[BetaManagedAgentsTextBlock(type="text", text="hello there")],
    )
    inner.beta.sessions.events.with_raw_response.send = AsyncMock(
        return_value=_raw_response(MagicMock(data=[sent_event]), headers={})
    )

    await client.send_user_message("sess_1", "hello there")

    assert client.get_workspace_id() is None


@pytest.mark.asyncio
async def test_create_agent_captures_rate_limit_headers_on_success(
    client: AnthropicClient,
) -> None:
    inner: Any = client._client
    inner.beta.agents.with_raw_response.create = AsyncMock(
        return_value=_raw_response(_Model({"id": "agent_1"}))
    )

    await client.create_agent(name="my-agent", model="claude-opus-4-6")

    status = client.get_create_rate_limit_status()
    assert status == CreateRateLimitInfo(
        limit=300,
        remaining=299,
        reset=datetime(2026, 6, 15, 9, 0, 0, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_create_agent_captures_rate_limit_headers_on_error(
    client: AnthropicClient,
) -> None:
    inner: Any = client._client
    error_headers = {
        "anthropic-ratelimit-requests-limit": "300",
        "anthropic-ratelimit-requests-remaining": "0",
        "anthropic-ratelimit-requests-reset": "2026-06-15T09:05:00Z",
    }
    inner.beta.agents.with_raw_response.create = AsyncMock(
        side_effect=_api_status_error(error_headers)
    )

    with pytest.raises(anthropic.APIStatusError):
        await client.create_agent(name="my-agent", model="claude-opus-4-6")

    status = client.get_create_rate_limit_status()
    assert status == CreateRateLimitInfo(
        limit=300,
        remaining=0,
        reset=datetime(2026, 6, 15, 9, 5, 0, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_create_agent_missing_rate_limit_headers_leaves_cache_none(
    client: AnthropicClient,
) -> None:
    inner: Any = client._client
    inner.beta.agents.with_raw_response.create = AsyncMock(
        return_value=_raw_response(_Model({"id": "agent_1"}), headers={})
    )

    await client.create_agent(name="my-agent", model="claude-opus-4-6")

    assert client.get_create_rate_limit_status() is None


def test_unwrap_webhook_without_secret_raises() -> None:
    instance = AnthropicClient(
        api_host="https://api.anthropic.com",
        api_key="test-api-key",
        webhook_signing_secret=None,
    )
    assert instance.has_webhook_secret is False
    with pytest.raises(ValueError):
        instance.unwrap_webhook("{}", {})
