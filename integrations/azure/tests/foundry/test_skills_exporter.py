from typing import Any
from unittest.mock import MagicMock

import pytest

from azure_integration.foundry.core.exporters.skills_exporter import SkillsExporter
from azure_integration.foundry.core.options import ListSkillsOptions


@pytest.mark.asyncio
async def test_skills_exporter_lists_with_feature_header() -> None:
    client = MagicMock()

    async def pages(*_args: Any, **_kwargs: Any) -> Any:
        yield [{"id": "skill-1", "name": "demo-skill", "created_at": 1731170000}]

    client.send_cursor_paginated_request = MagicMock(return_value=pages())
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
    assert collected[0]["name"] == "demo-skill"
    assert collected[0]["__foundryProjectName"] == "demo"
