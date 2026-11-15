from datetime import UTC, datetime
from typing import Any, AsyncIterator
from unittest.mock import MagicMock

import pytest

from azure_integration.foundry.clients.http.foundry_client import FoundryApiError
from azure_integration.foundry.core.exporters.conversations_exporter import (
    ConversationsExporter,
)
from azure_integration.foundry.core.exporters.responses_exporter import (
    ResponsesExporter,
)
from azure_integration.foundry.core.options import (
    ListConversationsOptions,
    ListResponsesOptions,
)

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
            raise FoundryApiError("Foundry API 400: no protocol")
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
