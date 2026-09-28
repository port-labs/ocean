from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx

from plain.client import PlainClient


def exporter_kinds() -> str:
    return Path(".port/spec.yaml").read_text()


def node_selection(query: str) -> str:
    return query.split("node {", 1)[1]


async def collect_pages(method: Any) -> list[list[dict[str, Any]]]:
    return [batch async for batch in method]


def make_client(config: dict[str, Any] | None = None) -> PlainClient:
    integration_config = {"api_token": "plainApiKey_test"}
    if config:
        integration_config.update(config)
    mock_ocean = MagicMock()
    mock_ocean.integration_config = integration_config
    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(500))
    )
    with patch("plain.client.ocean", mock_ocean):
        return PlainClient(http_client=http_client)
