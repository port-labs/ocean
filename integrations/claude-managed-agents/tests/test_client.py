from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from anthropic.types.beta.sessions.beta_managed_agents_text_block import (
    BetaManagedAgentsTextBlock,
)
from anthropic.types.beta.sessions.beta_managed_agents_user_message_event import (
    BetaManagedAgentsUserMessageEvent,
)

from clients.anthropic_client import AnthropicClient, SKILLS_BETA, _serialize


class _Model:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def to_dict(self) -> dict[str, Any]:
        return self._data


async def _aiter(items: list[Any]) -> AsyncGenerator[Any, None]:
    for item in items:
        yield item


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


def test_unwrap_webhook_without_secret_raises() -> None:
    instance = AnthropicClient(
        api_host="https://api.anthropic.com",
        api_key="test-api-key",
        webhook_signing_secret=None,
    )
    assert instance.has_webhook_secret is False
    with pytest.raises(ValueError):
        instance.unwrap_webhook("{}", {})


@pytest.mark.asyncio
async def test_get_skills_batches_results(client: AnthropicClient) -> None:
    inner: Any = client._client
    items = [_Model({"id": "s1"}), _Model({"id": "s2"}), _Model({"id": "s3"})]
    inner.beta.skills.list = AsyncMock(return_value=_aiter(items))

    batches = [batch async for batch in client.get_skills()]

    assert batches == [[{"id": "s1"}, {"id": "s2"}], [{"id": "s3"}]]
    inner.beta.skills.list.assert_awaited_once_with(
        source="custom",
        extra_headers={"anthropic-beta": SKILLS_BETA},
    )


@pytest.mark.asyncio
async def test_create_skill_uses_skills_beta_header(client: AnthropicClient) -> None:
    inner: Any = client._client
    inner.beta.skills.create = AsyncMock(return_value=_Model({"id": "skill_1"}))

    result = await client.create_skill(
        [("dir/SKILL.md", b"bytes")], display_title="Demo"
    )

    assert result == {"id": "skill_1"}
    inner.beta.skills.create.assert_awaited_once_with(
        files=[("dir/SKILL.md", b"bytes")],
        display_title="Demo",
        extra_headers={"anthropic-beta": SKILLS_BETA},
    )


@pytest.mark.asyncio
async def test_create_skill_version_uses_skills_beta_header(
    client: AnthropicClient,
) -> None:
    inner: Any = client._client
    inner.beta.skills.versions.create = AsyncMock(
        return_value=_Model({"id": "skillver_1"})
    )

    result = await client.create_skill_version("skill_1", [("dir/SKILL.md", b"bytes")])

    assert result == {"id": "skillver_1"}
    inner.beta.skills.versions.create.assert_awaited_once_with(
        "skill_1",
        files=[("dir/SKILL.md", b"bytes")],
        extra_headers={"anthropic-beta": SKILLS_BETA},
    )
