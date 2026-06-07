import sys
import types
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from integration import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

overrides_module = sys.modules.setdefault("overrides", types.ModuleType("overrides"))
setattr(overrides_module, "TeamResourceConfig", object)
setattr(overrides_module, "SLOResourceConfig", object)

from datadog.core.exporters.team_exporter import GetTeamOptions  # noqa: E402
from datadog.webhook.webhook_processors.audit_trails.team_webhook_processor import (  # noqa: E402
    TeamWebhookProcessor,
)


def _event(
    action: str,
    asset_id: str,
    asset_type: str = "team",
    evt_name: str = "Teams Management",
) -> dict[str, Any]:
    return {
        "attributes": {
            "evt": {"name": evt_name},
            "action": action,
            "asset": {"type": asset_type, "id": asset_id},
        }
    }


@pytest.fixture
def processor() -> TeamWebhookProcessor:
    return TeamWebhookProcessor(WebhookEvent(trace_id="test", payload={}, headers={}))


@pytest.fixture
def resource_config() -> SimpleNamespace:
    return SimpleNamespace(selector=SimpleNamespace(include_members=True))


@pytest.mark.asyncio
async def test_should_process_event_matches_team_type(
    processor: TeamWebhookProcessor,
) -> None:
    assert (
        await processor.should_process_event(
            WebhookEvent(trace_id="ok", payload=_event("modified", "t-1"), headers={})
        )
        is True
    )


@pytest.mark.asyncio
async def test_should_process_event_false_wrong_evt_name(
    processor: TeamWebhookProcessor,
) -> None:
    assert (
        await processor.should_process_event(
            WebhookEvent(
                trace_id="no",
                payload=_event("modified", "t-1", evt_name="Access Management"),
                headers={},
            )
        )
        is False
    )


@pytest.mark.asyncio
async def test_should_process_event_false_unsupported_action(
    processor: TeamWebhookProcessor,
) -> None:
    assert (
        await processor.should_process_event(
            WebhookEvent(trace_id="no", payload=_event("accessed", "t-1"), headers={})
        )
        is False
    )


@pytest.mark.asyncio
async def test_handle_single_event_fetches_team_with_members_flag(
    processor: TeamWebhookProcessor, resource_config: SimpleNamespace
) -> None:
    with patch(
        "datadog.webhook.webhook_processors.audit_trails.team_webhook_processor.TeamExporter"
    ) as cls:
        exporter = AsyncMock()
        exporter.get_resource.return_value = {"id": "t-1"}
        cls.return_value = exporter

        result = await processor.handle_event(
            _event("modified", "t-1"), resource_config=resource_config  # type: ignore[arg-type]
        )

    exporter.get_resource.assert_awaited_once_with(
        GetTeamOptions(resource_id="t-1", include_members=True)
    )
    assert result.updated_raw_results == [{"id": "t-1"}]
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_get_matching_kinds(processor: TeamWebhookProcessor) -> None:
    assert await processor.get_matching_kinds(
        WebhookEvent(trace_id="x", payload={}, headers={})
    ) == [ObjectKind.TEAM]
