import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from integration import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

# The production module imports these typing aliases from a top-level `overrides` module.
overrides_module = sys.modules.setdefault("overrides", types.ModuleType("overrides"))
setattr(overrides_module, "TeamResourceConfig", object)
setattr(overrides_module, "SLOResourceConfig", object)

from datadog.core.exporters.team_exporter import GetTeamOptions
from datadog.webhook.webhook_processors.audit_trails.team_webhook_processor import (
    TeamWebhookProcessor,
)


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
    event = WebhookEvent(
        trace_id="ok",
        payload={"event": {"action": "resource.modify", "asset": {"type": "team"}}},
        headers={},
    )
    assert await processor.should_process_event(event) is True


@pytest.mark.asyncio
async def test_handle_event_with_delete_action_returns_deleted(
    processor: TeamWebhookProcessor, resource_config: SimpleNamespace
) -> None:
    result = await processor.handle_event(
        {"event": {"action": "resource.destroy", "asset": {"id": "t-1"}}},
        resource_config=resource_config,
    )
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"id": "t-1"}]


@pytest.mark.asyncio
async def test_handle_event_fetches_team_with_members_flag(
    processor: TeamWebhookProcessor, resource_config: SimpleNamespace
) -> None:
    with (
        patch(
            "datadog.webhook.webhook_processors.audit_trails.team_webhook_processor.init_client",
            return_value=AsyncMock(),
        ),
        patch(
            "datadog.webhook.webhook_processors.audit_trails.team_webhook_processor.TeamExporter"
        ) as exporter_cls,
    ):
        exporter = AsyncMock()
        exporter.get_resource.return_value = {"id": "t-1"}
        exporter_cls.return_value = exporter

        result = await processor.handle_event(
            {"event": {"action": "resource.update", "asset": {"id": "t-1"}}},
            resource_config=resource_config,
        )

    exporter.get_resource.assert_awaited_once_with(
        GetTeamOptions(id="t-1", include_members=True)
    )
    assert result.updated_raw_results == [{"id": "t-1"}]
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_event_converts_404_to_deleted(
    processor: TeamWebhookProcessor, resource_config: SimpleNamespace
) -> None:
    error_response = httpx.Response(
        404, request=httpx.Request("GET", "https://api.datadoghq.com/api/v2/team/t-1")
    )
    not_found = httpx.HTTPStatusError(
        "not found",
        request=error_response.request,
        response=error_response,
    )
    with (
        patch(
            "datadog.webhook.webhook_processors.audit_trails.team_webhook_processor.init_client",
            return_value=AsyncMock(),
        ),
        patch(
            "datadog.webhook.webhook_processors.audit_trails.team_webhook_processor.TeamExporter"
        ) as exporter_cls,
    ):
        exporter = AsyncMock()
        exporter.get_resource.side_effect = not_found
        exporter_cls.return_value = exporter

        result = await processor.handle_event(
            {"event": {"action": "resource.update", "asset": {"id": "t-1"}}},
            resource_config=resource_config,
        )

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"id": "t-1"}]


@pytest.mark.asyncio
async def test_get_matching_kinds_and_validate_payload(
    processor: TeamWebhookProcessor,
) -> None:
    assert await processor.get_matching_kinds(
        WebhookEvent(trace_id="x", payload={}, headers={})
    ) == [ObjectKind.TEAM]
    assert await processor.validate_payload({"event": {"asset": {"id": "t-1"}}}) is True
    assert await processor.validate_payload({"event": {"asset": {}}}) is False
