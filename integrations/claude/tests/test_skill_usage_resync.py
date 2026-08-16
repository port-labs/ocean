from collections.abc import AsyncGenerator, AsyncIterator, Callable
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from core.exceptions import ClaudeSkillUsageResyncError


@pytest.fixture(autouse=True)
def _initialize_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.event_listener.should_resync = True
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.mark.asyncio
async def test_on_resync_skill_usage_raises_after_partial_day_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with (
        patch(
            "port_ocean.context.ocean.ocean.integration.on_resync",
            lambda fn, kind=None: fn,
        ),
        patch(
            "port_ocean.context.ocean.ocean.integration.on_start",
            lambda fn: fn,
        ),
    ):
        import main

    mock_resource_config = MagicMock()
    mock_resource_config.selector.starting_date = None
    mock_resource_config.selector.time_frame = 2

    monkeypatch.setattr(main, "event", MagicMock(resource_config=mock_resource_config))
    monkeypatch.setattr(main, "is_deployment_enabled", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        main,
        "get_skill_usage_dates",
        lambda **_kwargs: ["2026-03-01", "2026-03-02"],
    )

    class FakeExporter:
        async def get_paginated_resources(
            self, options: dict[str, str | int]
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            if options["date"] == "2026-03-01":
                raise RuntimeError("API unavailable")
            yield [{"skill_name": "contribute-docs"}]

    monkeypatch.setattr(main, "create_skill_usage_exporter", lambda: FakeExporter())

    resync = cast(
        Callable[[str], AsyncIterator[list[dict[str, Any]]]],
        main.on_resync_skill_usage,
    )
    pages: list[list[dict[str, Any]]] = []
    with pytest.raises(ClaudeSkillUsageResyncError, match="2026-03-01"):
        async for page in resync("claude-ai-skill-usage"):
            pages.append(page)

    assert pages == [[{"skill_name": "contribute-docs"}]]
