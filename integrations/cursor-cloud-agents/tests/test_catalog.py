from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.catalog import (
    enrich_v0_agent_raw_for_catalog,
    fetch_run_raw_for_catalog,
    normalize_agent_raw_for_catalog,
)


def test_enrich_v0_agent_raw_maps_source_and_target_to_v1_fields() -> None:
    raw = {
        "id": "bc-1",
        "name": "Ok response handling",
        "status": "CREATING",
        "source": {"repository": "https://github.com/org/repo", "ref": "main"},
        "target": {"url": "https://cursor.com/agents?id=bc-1"},
        "createdAt": "2026-07-16T11:11:03.025Z",
    }

    enriched = enrich_v0_agent_raw_for_catalog(raw, console_host="https://cursor.com")

    assert enriched["repos"] == [{"url": "https://github.com/org/repo"}]
    assert enriched["url"] == "https://cursor.com/agents?id=bc-1"


def test_enrich_v0_agent_raw_builds_url_from_console_host() -> None:
    raw = {
        "id": "bc-1",
        "source": {"repository": "https://github.com/org/repo"},
    }

    enriched = enrich_v0_agent_raw_for_catalog(raw, console_host="https://cursor.com/")

    assert enriched["url"] == "https://cursor.com/agents/bc-1"


def test_normalize_agent_raw_maps_v0_creating_to_active() -> None:
    raw = {
        "id": "bc-1",
        "name": "Ok response handling",
        "status": "CREATING",
        "source": {"repository": "https://github.com/org/repo"},
        "target": {"url": "https://cursor.com/agents?id=bc-1"},
        "createdAt": "2026-07-16T11:11:03.025Z",
        "updatedAt": None,
    }

    normalized = normalize_agent_raw_for_catalog(raw, console_host="https://cursor.com")

    assert normalized == {
        "id": "bc-1",
        "name": "Ok response handling",
        "status": "ACTIVE",
        "source": {"repository": "https://github.com/org/repo"},
        "target": {"url": "https://cursor.com/agents?id=bc-1"},
        "repos": [{"url": "https://github.com/org/repo"}],
        "url": "https://cursor.com/agents?id=bc-1",
        "createdAt": "2026-07-16T11:11:03.025Z",
    }


def test_normalize_agent_raw_preserves_v1_statuses() -> None:
    assert (
        normalize_agent_raw_for_catalog({"id": "bc-1", "status": "ARCHIVED"})["status"]
        == "ARCHIVED"
    )
    assert (
        normalize_agent_raw_for_catalog({"id": "bc-1", "status": "ACTIVE"})["status"]
        == "ACTIVE"
    )


@pytest.mark.asyncio
async def test_fetch_run_raw_for_catalog_attaches_usage() -> None:
    client = MagicMock()
    client.send_api_request = AsyncMock(
        side_effect=[
            {"id": "run-1", "status": "FINISHED", "agentId": "bc-1"},
            {
                "runs": [
                    {
                        "id": "run-1",
                        "usage": {
                            "inputTokens": 10,
                            "outputTokens": 20,
                            "totalTokens": 30,
                        },
                    }
                ]
            },
        ]
    )

    run_raw = await fetch_run_raw_for_catalog(client, "bc-1", "run-1", status="ERROR")

    assert run_raw["status"] == "FINISHED"
    assert run_raw["usage"] == {
        "inputTokens": 10,
        "outputTokens": 20,
        "totalTokens": 30,
    }
    assert client.send_api_request.await_count == 2


@pytest.mark.asyncio
async def test_fetch_run_raw_for_catalog_falls_back_to_webhook_fields() -> None:
    client = MagicMock()
    client.send_api_request = AsyncMock(
        side_effect=[RuntimeError("boom"), {"runs": []}]
    )
    webhook_time = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)

    run_raw = await fetch_run_raw_for_catalog(
        client,
        "bc-1",
        "run-1",
        status="FINISHED",
        updated_at=webhook_time,
    )

    assert run_raw == {
        "id": "run-1",
        "agentId": "bc-1",
        "status": "FINISHED",
        "updatedAt": "2025-06-01T12:00:00Z",
    }
