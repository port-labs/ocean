from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from azure_integration.foundry.core.exporters.toolboxes_exporter import (
    ToolboxesExporter,
)
from azure_integration.foundry.core.options import ListToolboxesOptions

_PROJECT = "https://acct.services.ai.azure.com/api/projects/demo/"
_A2A_TARGET = (
    "https://acct.services.ai.azure.com/api/projects/other-proj/agents/"
    "sub-agent/endpoint/protocols/a2a"
)


@pytest.mark.asyncio
async def test_toolboxes_exporter_enriches_skills_and_a2a() -> None:
    client = MagicMock()

    async def list_pages(*_args: Any, **_kwargs: Any) -> Any:
        yield [{"name": "main-toolbox"}]

    client.send_cursor_paginated_request = MagicMock(return_value=list_pages())

    async def send_api_request(url: str, **_kwargs: Any) -> dict[str, Any]:
        if url.endswith("/toolboxes/main-toolbox"):
            return {
                "name": "main-toolbox",
                "versions": {
                    "latest": {
                        "skills": ["skill-a", {"name": "skill-b"}],
                        "tools": [
                            {
                                "type": "a2a",
                                "project_connection_id": (
                                    "/subscriptions/s/resourceGroups/rg/providers/"
                                    "Microsoft.CognitiveServices/accounts/acct/"
                                    "projects/demo/connections/to-sub-agent"
                                ),
                            }
                        ],
                    }
                },
            }
        if url.endswith("/connections/to-sub-agent"):
            return {"target": _A2A_TARGET, "type": "RemoteA2A"}
        return {}

    client.send_api_request = AsyncMock(side_effect=send_api_request)
    exporter = ToolboxesExporter(client)
    batches: list[dict[str, Any]] = []
    async for batch in exporter.get_paginated_resources(
        ListToolboxesOptions(
            project_endpoint=_PROJECT,
            project_id="/subscriptions/s/rg/acct/projects/demo",
        )
    ):
        batches.extend(batch)

    toolbox = batches[0]
    assert toolbox["__skillNames"] == ["skill-a", "skill-b"]
    assert toolbox["__a2aSubagents"] == [
        {
            "connectionName": "to-sub-agent",
            "target": _A2A_TARGET,
            "projectName": "other-proj",
            "agentName": "sub-agent",
        }
    ]
