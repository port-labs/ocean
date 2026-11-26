from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from azure_integration.foundry.core.exporters.agents_exporter import AgentsExporter
from azure_integration.foundry.core.options import ListAgentsOptions

_PROJECT = "https://example.services.ai.azure.com/api/projects/demo"
_PROJECT_ID = "demo"


async def _agen(*pages: list[dict[str, Any]]) -> AsyncIterator[list[dict[str, Any]]]:
    for page in pages:
        yield page


@pytest.mark.asyncio
async def test_enrich_toolbox_false_skips_toolbox_api() -> None:
    client = MagicMock()
    client.send_cursor_paginated_request = MagicMock(
        return_value=_agen([{"id": "agent-a", "name": "Agent"}])
    )
    client.send_api_request = AsyncMock()

    async for _ in AgentsExporter(client).get_paginated_resources(
        ListAgentsOptions(
            project_endpoint=_PROJECT,
            project_id=_PROJECT_ID,
            enrich_toolbox=False,
        )
    ):
        pass

    client.send_api_request.assert_not_awaited()


@pytest.mark.asyncio
async def test_enrich_toolbox_adds_skills_and_mcp_labels() -> None:
    toolbox_url = f"{_PROJECT}/toolboxes/my-tb/versions/2/mcp"
    client = MagicMock()

    async def cursor_paginated(
        _endpoint: str, resource: str, **_kwargs: Any
    ) -> AsyncIterator[list[dict[str, Any]]]:
        if resource == "toolboxes":
            yield [
                {
                    "name": "my-tb",
                    "versions": {
                        "latest": {
                            "skills": ["skill-a"],
                            "tools": [
                                {
                                    "type": "mcp",
                                    "server_label": "github",
                                    "server_url": "https://mcp.example/github",
                                },
                                {
                                    "type": "mcp",
                                    "server_label": "port-mcps",
                                    "server_url": toolbox_url,
                                },
                                {"type": "function", "name": "fn"},
                            ],
                        }
                    },
                }
            ]
            return
        assert resource == "agents"
        yield [
            {
                "id": "agent-a",
                "versions": {
                    "latest": {
                        "definition": {
                            "kind": "prompt",
                            "tools": [
                                {
                                    "type": "mcp",
                                    "server_label": "port-mcps",
                                    "server_url": toolbox_url,
                                }
                            ],
                        }
                    }
                },
            }
        ]

    client.send_cursor_paginated_request = MagicMock(side_effect=cursor_paginated)
    client.send_api_request = AsyncMock(return_value={})

    pages: list[list[dict[str, Any]]] = []
    async for page in AgentsExporter(client).get_paginated_resources(
        ListAgentsOptions(
            project_endpoint=_PROJECT,
            project_id=_PROJECT_ID,
            enrich_toolbox=True,
        )
    ):
        pages.append(page)

    assert pages[0][0]["__skillNames"] == ["skill-a"]
    assert pages[0][0]["__mcpUrls"] == ["https://mcp.example/github"]
    assert pages[0][0]["__a2aSubagents"] == []
