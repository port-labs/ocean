import io
import zipfile
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from azure_integration.foundry.core.exporters.skills_exporter import SkillsExporter
from azure_integration.foundry.core.options import ListSkillsOptions


def _skill_zip(body: str = "# demo\n") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("SKILL.md", body)
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_skills_exporter_lists_with_feature_header_and_markdown() -> None:
    client = MagicMock()

    async def pages(*_args: Any, **_kwargs: Any) -> Any:
        yield [{"id": "skill-1", "name": "demo-skill", "created_at": 1731170000}]

    client.send_cursor_paginated_request = MagicMock(return_value=pages())
    client.send_bytes_request = AsyncMock(return_value=_skill_zip("# hello skill\n"))
    exporter = SkillsExporter(client)
    collected: list[dict[str, Any]] = []
    async for batch in exporter.get_paginated_resources(
        ListSkillsOptions(
            project_endpoint="https://example/api/projects/demo/",
            project_id="/subscriptions/s/rg/acct/projects/demo",
        )
    ):
        collected.extend(batch)

    client.send_cursor_paginated_request.assert_called_once()
    _, kwargs = client.send_cursor_paginated_request.call_args
    assert kwargs["extra_headers"] == {"Foundry-Features": "Skills=V1Preview"}
    client.send_bytes_request.assert_awaited_once()
    bytes_url = client.send_bytes_request.await_args.args[0]
    assert bytes_url.endswith("/skills/demo-skill/content")
    assert collected[0]["name"] == "demo-skill"
    assert collected[0]["__foundryProjectName"] == "demo"
    assert collected[0]["__skillMarkdown"] == "# hello skill\n"
