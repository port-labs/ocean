from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from azure_integration.foundry.core.exporters.agents_exporter import AgentsExporter


@pytest.mark.asyncio
async def test_attach_versions_keeps_raw_version_payload() -> None:
    agent: dict[str, Any] = {"id": "Omby-agent", "name": "Omby-agent"}
    client = MagicMock()
    client.send_api_request = AsyncMock(
        return_value={
            "data": [
                {
                    "version": "6",
                    "status": "active",
                    "definition": {"kind": "prompt", "model": "gpt-5"},
                }
            ]
        }
    )
    client.items_from_payload.side_effect = lambda payload: payload["data"]

    await AgentsExporter(client)._attach_versions("https://example", [agent])

    client.send_api_request.assert_awaited_once_with(
        "https://example/agents/Omby-agent/versions"
    )
    assert agent["__versions"] == [
        {
            "version": "6",
            "status": "active",
            "definition": {"kind": "prompt", "model": "gpt-5"},
        }
    ]
    assert "versions" not in agent
