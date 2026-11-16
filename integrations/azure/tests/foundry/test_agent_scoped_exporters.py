from datetime import UTC, datetime
from typing import Any, AsyncIterator
from unittest.mock import MagicMock

import pytest
from pydantic.v1 import ValidationError

from azure_integration.foundry.clients.http.foundry_client import FoundryApiError
from azure_integration.foundry.core.exporters.conversations_exporter import (
    ConversationsExporter,
)
from azure_integration.foundry.core.exporters.responses_exporter import (
    ResponsesExporter,
)
from azure_integration.foundry.core.options import (
    EndpointScope,
    ListConversationsOptions,
    ListResponsesOptions,
)
from azure_integration.foundry.kinds import ConversationSelector

_NOW = int(datetime.now(UTC).timestamp())
_PROJECT = "https://example.services.ai.azure.com/api/projects/demo"
_PROJECT_ID = "demo-project"


async def _agen(*pages: list[dict[str, Any]]) -> AsyncIterator[list[dict[str, Any]]]:
    for page in pages:
        yield page


@pytest.mark.asyncio
async def test_lists_conversations_per_agent_endpoint() -> None:
    client = MagicMock()
    client.send_cursor_paginated_request = MagicMock(
        side_effect=[
            _agen([{"id": "agent-a"}]),
            _agen([{"id": "conv-1", "created_at": _NOW}]),
        ]
    )

    pages: list[list[dict[str, Any]]] = []
    async for page in ConversationsExporter(client).get_paginated_resources(
        ListConversationsOptions(
            project_endpoint=_PROJECT,
            project_id=_PROJECT_ID,
            since_days=30,
        )
    ):
        pages.append(page)

    assert client.send_cursor_paginated_request.call_args_list[1].args[1] == (
        "agents/agent-a/endpoint/protocols/openai/conversations"
    )
    assert pages[0][0]["id"] == "conv-1"
    assert pages[0][0]["__foundryAgentId"] == "agent-a"


@pytest.mark.asyncio
async def test_lists_conversations_project_scope_only() -> None:
    client = MagicMock()
    client.send_cursor_paginated_request = MagicMock(
        side_effect=[_agen([{"id": "conv-p", "created_at": _NOW}])]
    )

    pages: list[list[dict[str, Any]]] = []
    async for page in ConversationsExporter(client).get_paginated_resources(
        ListConversationsOptions(
            project_endpoint=_PROJECT,
            project_id=_PROJECT_ID,
            since_days=30,
            endpoint_scopes=[EndpointScope.PROJECT],
        )
    ):
        pages.append(page)

    assert client.send_cursor_paginated_request.call_count == 1
    assert client.send_cursor_paginated_request.call_args.args[1] == (
        "openai/v1/conversations"
    )
    assert pages[0][0]["id"] == "conv-p"
    assert "__foundryAgentId" not in pages[0][0]


@pytest.mark.asyncio
async def test_lists_conversations_both_scopes_are_separate_stores() -> None:
    client = MagicMock()
    client.send_cursor_paginated_request = MagicMock(
        side_effect=[
            _agen([{"id": "agent-a"}]),
            _agen([{"id": "agent-conv", "created_at": _NOW}]),
            _agen([{"id": "project-conv", "created_at": _NOW}]),
        ]
    )

    pages: list[list[dict[str, Any]]] = []
    async for page in ConversationsExporter(client).get_paginated_resources(
        ListConversationsOptions(
            project_endpoint=_PROJECT,
            project_id=_PROJECT_ID,
            since_days=30,
            endpoint_scopes=[EndpointScope.AGENT, EndpointScope.PROJECT],
        )
    ):
        pages.append(page)

    paths = [
        call.args[1] for call in client.send_cursor_paginated_request.call_args_list
    ]
    assert paths == [
        "agents",
        "agents/agent-a/endpoint/protocols/openai/conversations",
        "openai/v1/conversations",
    ]
    assert pages[0][0]["id"] == "agent-conv"
    assert pages[0][0]["__foundryAgentId"] == "agent-a"
    assert pages[1][0]["id"] == "project-conv"
    assert "__foundryAgentId" not in pages[1][0]


@pytest.mark.asyncio
async def test_lists_responses_per_agent_endpoint() -> None:
    client = MagicMock()
    client.send_cursor_paginated_request = MagicMock(
        side_effect=[
            _agen([{"id": "agent-a"}]),
            _agen([{"id": "resp-1", "created_at": _NOW}]),
        ]
    )

    pages: list[list[dict[str, Any]]] = []
    async for page in ResponsesExporter(client).get_paginated_resources(
        ListResponsesOptions(
            project_endpoint=_PROJECT,
            project_id=_PROJECT_ID,
            since_days=30,
        )
    ):
        pages.append(page)

    assert client.send_cursor_paginated_request.call_args_list[1].args[1] == (
        "agents/agent-a/endpoint/protocols/openai/responses"
    )
    assert pages[0][0]["id"] == "resp-1"
    assert pages[0][0]["__foundryAgentId"] == "agent-a"


@pytest.mark.asyncio
async def test_skips_agent_when_protocol_endpoint_errors() -> None:
    async def fail_then_ok(
        project_endpoint: str, path: str, **kwargs: Any
    ) -> AsyncIterator[list[dict[str, Any]]]:
        del project_endpoint, kwargs
        if path == "agents":
            yield [{"id": "bad-agent"}, {"id": "good-agent"}]
            return
        if "bad-agent" in path:
            raise FoundryApiError("Foundry API 400: no protocol", status_code=400)
        yield [{"id": "resp-ok", "created_at": _NOW}]

    client = MagicMock()
    client.send_cursor_paginated_request = MagicMock(side_effect=fail_then_ok)

    pages: list[list[dict[str, Any]]] = []
    async for page in ResponsesExporter(client).get_paginated_resources(
        ListResponsesOptions(
            project_endpoint=_PROJECT,
            project_id=_PROJECT_ID,
            since_days=7,
        )
    ):
        pages.append(page)

    assert len(pages) == 1
    assert pages[0][0]["id"] == "resp-ok"
    assert pages[0][0]["__foundryAgentId"] == "good-agent"


@pytest.mark.asyncio
async def test_rethrows_non_skippable_agent_protocol_errors() -> None:
    async def fail_server(
        project_endpoint: str, path: str, **kwargs: Any
    ) -> AsyncIterator[list[dict[str, Any]]]:
        del project_endpoint, kwargs
        if path == "agents":
            yield [{"id": "agent-a"}]
            return
        raise FoundryApiError("Foundry API 500: boom", status_code=500)

    client = MagicMock()
    client.send_cursor_paginated_request = MagicMock(side_effect=fail_server)

    with pytest.raises(FoundryApiError, match="500"):
        async for _ in ResponsesExporter(client).get_paginated_resources(
            ListResponsesOptions(
                project_endpoint=_PROJECT,
                project_id=_PROJECT_ID,
                since_days=7,
            )
        ):
            pass


def test_endpoint_scopes_default_agent() -> None:
    selector = ConversationSelector(query="true")
    assert selector.endpoint_scopes == ["agent"]


def test_endpoint_scopes_rejects_duplicates() -> None:
    with pytest.raises(ValidationError, match="duplicate"):
        ConversationSelector(
            query="true",
            endpointScopes=[EndpointScope.AGENT, EndpointScope.AGENT],
        )
