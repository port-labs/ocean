from pathlib import Path
from typing import Any


def exporter_kinds() -> str:
    return Path(".port/spec.yaml").read_text()


def node_selection(query: str) -> str:
    return query.split("node {", 1)[1]


async def collect_pages(method: Any) -> list[list[dict[str, Any]]]:
    return [batch async for batch in method]
