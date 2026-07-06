from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from anthropic.types.beta.sessions.beta_managed_agents_text_block import (
    BetaManagedAgentsTextBlock,
)
from anthropic.types.beta.sessions.beta_managed_agents_user_message_event import (
    BetaManagedAgentsUserMessageEvent,
)

from clients.anthropic_client import AnthropicClient, RateLimitInfo
from clients.exceptions import (
    UnexpectedApiResponseError,
    WebhookSigningSecretNotConfiguredError,
)


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


def _response(
    method: str, headers: dict[str, str], status_code: int = 200
) -> httpx.Response:
    request = httpx.Request(method, "https://api.anthropic.com/v1/agents")
    return httpx.Response(status_code, headers=headers, request=request)


@pytest.fixture
def client() -> AnthropicClient:
    instance = AnthropicClient(
        api_host="https://api.anthropic.com",
        api_key="test-api-key",
        console_host="https://platform.claude.com",
        webhook_signing_secret="whsec_test",
        page_size=2,
    )
    instance._client = MagicMock()
    return instance


def test_get_console_host_strips_trailing_slash() -> None:
    instance = AnthropicClient(
        api_host="https://api.anthropic.com",
        api_key="test-api-key",
        console_host="https://platform.claude.com/",
    )
    assert instance.get_console_host() == "https://platform.claude.com"


def test_beta_property_exposes_sdk_namespace(client: AnthropicClient) -> None:
    inner: Any = client._client

    assert client.beta is inner.beta


@pytest.mark.asyncio
async def test_paginate_batches_results(client: AnthropicClient) -> None:
    items = [_Model({"id": "a1"}), _Model({"id": "a2"}), _Model({"id": "a3"})]

    async def _list_call() -> AsyncGenerator[Any, None]:
        return _aiter(items)

    batches = [batch async for batch in client.paginate(_list_call())]

    assert batches == [[{"id": "a1"}, {"id": "a2"}], [{"id": "a3"}]]


@pytest.mark.asyncio
async def test_paginate_yields_nothing_for_empty_paginator(
    client: AnthropicClient,
) -> None:
    async def _list_call() -> AsyncGenerator[Any, None]:
        return _aiter([])

    batches = [batch async for batch in client.paginate(_list_call())]

    assert batches == []


@pytest.mark.asyncio
async def test_get_session_serializes_result(client: AnthropicClient) -> None:
    inner: Any = client._client
    inner.beta.sessions.retrieve = AsyncMock(return_value=_Model({"id": "sess_1"}))

    result = await client.get_session("sess_1")

    assert result == {"id": "sess_1"}
    inner.beta.sessions.retrieve.assert_awaited_once_with("sess_1")


@pytest.mark.asyncio
async def test_get_vault_serializes_result(client: AnthropicClient) -> None:
    inner: Any = client._client
    inner.beta.vaults.retrieve = AsyncMock(return_value=_Model({"id": "vault_1"}))

    result = await client.get_vault("vault_1")

    assert result == {"id": "vault_1"}
    inner.beta.vaults.retrieve.assert_awaited_once_with("vault_1")


@pytest.mark.asyncio
async def test_get_session_events_omits_unset_filters(
    client: AnthropicClient,
) -> None:
    inner: Any = client._client
    inner.beta.sessions.events.list = AsyncMock(return_value=_aiter([]))

    [batch async for batch in client.get_session_events("sess_1")]

    inner.beta.sessions.events.list.assert_awaited_once_with("sess_1")


@pytest.mark.asyncio
async def test_get_session_events_forwards_provided_filters(
    client: AnthropicClient,
) -> None:
    inner: Any = client._client
    inner.beta.sessions.events.list = AsyncMock(return_value=_aiter([]))
    before = datetime(2026, 6, 15, 9, 0, 0, tzinfo=timezone.utc)

    [
        batch
        async for batch in client.get_session_events(
            "sess_1",
            types=["session.status_idle"],
            order="desc",
            created_at_lt=before,
            limit=1,
        )
    ]

    inner.beta.sessions.events.list.assert_awaited_once_with(
        "sess_1",
        types=["session.status_idle"],
        order="desc",
        created_at_lt=before,
        limit=1,
    )


@pytest.mark.asyncio
async def test_create_agent_builds_payload_and_drops_none(
    client: AnthropicClient,
) -> None:
    inner: Any = client._client
    inner.beta.agents.create = AsyncMock(return_value=_Model({"id": "agent_1"}))

    result = await client.create_agent(
        name="my-agent",
        model="claude-opus-4-6",
        system="be helpful",
        extra={"description": "demo", "metadata": None},
    )

    assert result == {"id": "agent_1"}
    inner.beta.agents.create.assert_awaited_once_with(
        name="my-agent",
        model="claude-opus-4-6",
        system="be helpful",
        description="demo",
    )


@pytest.mark.asyncio
async def test_create_session_builds_payload(client: AnthropicClient) -> None:
    inner: Any = client._client
    inner.beta.sessions.create = AsyncMock(return_value=_Model({"id": "sess_1"}))

    result = await client.create_session("agent_1", "env_1")

    assert result == {"id": "sess_1"}
    inner.beta.sessions.create.assert_awaited_once_with(
        agent="agent_1", environment_id="env_1"
    )


@pytest.mark.asyncio
async def test_create_session_forwards_extra(client: AnthropicClient) -> None:
    inner: Any = client._client
    inner.beta.sessions.create = AsyncMock(return_value=_Model({"id": "sess_1"}))

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

    inner.beta.sessions.create.assert_awaited_once_with(
        agent="agent_1",
        environment_id="env_1",
        title="Demo",
        metadata={"owner": "port"},
        vault_ids=["vault_1"],
        resources=[{"type": "memory_store", "memory_store_id": "ms_1"}],
    )


@pytest.mark.asyncio
async def test_send_user_message_event_shape(client: AnthropicClient) -> None:
    inner: Any = client._client
    sent_event = BetaManagedAgentsUserMessageEvent(
        id="evt_1",
        type="user.message",
        content=[BetaManagedAgentsTextBlock(type="text", text="hello there")],
    )
    inner.beta.sessions.events.send = AsyncMock(
        return_value=MagicMock(data=[sent_event])
    )

    result = await client.send_user_message("sess_1", "hello there")

    assert result.id == "evt_1"
    inner.beta.sessions.events.send.assert_awaited_once_with(
        "sess_1",
        events=[
            {
                "type": "user.message",
                "content": [{"type": "text", "text": "hello there"}],
            }
        ],
    )


@pytest.mark.asyncio
async def test_send_user_message_raises_when_no_event_returned(
    client: AnthropicClient,
) -> None:
    inner: Any = client._client
    inner.beta.sessions.events.send = AsyncMock(return_value=MagicMock(data=[]))

    with pytest.raises(UnexpectedApiResponseError, match="no event was returned"):
        await client.send_user_message("sess_1", "hello there")


@pytest.mark.asyncio
async def test_send_user_message_raises_on_unexpected_event_type(
    client: AnthropicClient,
) -> None:
    inner: Any = client._client
    unexpected_event = MagicMock(type="session.status_idle")
    inner.beta.sessions.events.send = AsyncMock(
        return_value=MagicMock(data=[unexpected_event])
    )

    with pytest.raises(UnexpectedApiResponseError, match="session.status_idle"):
        await client.send_user_message("sess_1", "hello there")


def test_unwrap_webhook_without_secret_raises() -> None:
    instance = AnthropicClient(
        api_host="https://api.anthropic.com",
        api_key="test-api-key",
        console_host="https://platform.claude.com",
        webhook_signing_secret=None,
    )
    assert instance.has_webhook_secret is False
    with pytest.raises(WebhookSigningSecretNotConfiguredError):
        instance.unwrap_webhook("{}", {})


# --- Rate limit + workspace-id capture, via the request/response hooks -----
#
# These are exercised directly against `_on_request`/`_on_response` rather
# than through `create_agent`/`send_user_message`/etc., since the hooks fire
# on every HTTP call the client makes (including every page of a paginated
# `list()` call), regardless of which method triggered it.


@pytest.mark.asyncio
async def test_on_response_captures_create_rate_limit_headers_for_non_get(
    client: AnthropicClient,
) -> None:
    await client._on_response(_response("POST", _RATE_LIMIT_HEADERS))

    assert client.get_create_rate_limit_status() == RateLimitInfo(
        limit=300,
        remaining=299,
        reset=datetime(2026, 6, 15, 9, 0, 0, tzinfo=timezone.utc),
    )
    assert client.get_read_rate_limit_status() is None


@pytest.mark.asyncio
async def test_on_response_captures_read_rate_limit_headers_for_get(
    client: AnthropicClient,
) -> None:
    await client._on_response(_response("GET", _RATE_LIMIT_HEADERS))

    assert client.get_read_rate_limit_status() == RateLimitInfo(
        limit=300,
        remaining=299,
        reset=datetime(2026, 6, 15, 9, 0, 0, tzinfo=timezone.utc),
    )
    assert client.get_create_rate_limit_status() is None


@pytest.mark.asyncio
async def test_on_response_captures_headers_on_error_status(
    client: AnthropicClient,
) -> None:
    await client._on_response(_response("POST", _RATE_LIMIT_HEADERS, status_code=429))

    assert client.get_create_rate_limit_status() is not None


@pytest.mark.asyncio
async def test_on_response_ignores_missing_rate_limit_headers(
    client: AnthropicClient,
) -> None:
    await client._on_response(_response("GET", {}))

    assert client.get_read_rate_limit_status() is None


@pytest.mark.asyncio
async def test_on_response_captures_workspace_id(client: AnthropicClient) -> None:
    await client._on_response(_response("POST", {"anthropic-workspace-id": "ws_1"}))

    assert client.get_workspace_id() == "ws_1"


@pytest.mark.asyncio
async def test_on_response_missing_workspace_id_leaves_cache_none(
    client: AnthropicClient,
) -> None:
    await client._on_response(_response("POST", {}))

    assert client.get_workspace_id() is None


@pytest.mark.asyncio
async def test_on_request_noop_when_no_cached_info(client: AnthropicClient) -> None:
    request = httpx.Request("GET", "https://api.anthropic.com/v1/agents")

    await client._on_request(request)

    assert client.get_read_rate_limit_status() is None


@pytest.mark.asyncio
async def test_on_request_optimistically_decrements_remaining(
    client: AnthropicClient,
) -> None:
    client._read_rate_limit_info = RateLimitInfo(
        limit=1200,
        remaining=5,
        reset=datetime.now(timezone.utc) + timedelta(seconds=30),
    )
    request = httpx.Request("GET", "https://api.anthropic.com/v1/agents")

    await client._on_request(request)

    status = client.get_read_rate_limit_status()
    assert status is not None
    assert status.remaining == 4


@pytest.mark.asyncio
async def test_on_request_sleeps_when_pool_exhausted(
    client: AnthropicClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sleep_calls: list[float] = []

    async def _fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr("clients.anthropic_client.asyncio.sleep", _fake_sleep)

    client._create_rate_limit_info = RateLimitInfo(
        limit=300, remaining=0, reset=datetime.now(timezone.utc) + timedelta(seconds=10)
    )
    request = httpx.Request("POST", "https://api.anthropic.com/v1/agents")

    await client._on_request(request)

    assert len(sleep_calls) == 1
    assert 9 <= sleep_calls[0] <= 10
    assert client.get_create_rate_limit_status() is None


@pytest.mark.asyncio
async def test_on_request_does_not_sleep_once_reset_has_passed(
    client: AnthropicClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    slept = False

    async def _fake_sleep(seconds: float) -> None:
        nonlocal slept
        slept = True

    monkeypatch.setattr("clients.anthropic_client.asyncio.sleep", _fake_sleep)

    client._read_rate_limit_info = RateLimitInfo(
        limit=1200, remaining=0, reset=datetime.now(timezone.utc) - timedelta(seconds=5)
    )
    request = httpx.Request("GET", "https://api.anthropic.com/v1/agents")

    await client._on_request(request)

    assert slept is False
    assert client.get_read_rate_limit_status() is None
