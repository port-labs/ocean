from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from pydantic import ValidationError
from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient
from azure_integration.foundry.core.exporters.responses_exporter import ResponsesExporter
from azure_integration.foundry.foundry_incremental import RESPONSE_INCREMENTAL
from azure_integration.foundry.helpers.utils import effective_conversation_cutoff
from azure_integration.foundry.models.responses import Response


def conversation_latest_keys(response: Response) -> dict[str, Any]:
    keys: dict[str, Any] = {}
    if response.id:
        keys["__latestResponseId"] = response.id
    if response.status:
        keys["__latestResponseStatus"] = response.status
    if (duration := response.active_duration_seconds()) > 0:
        keys["__latestResponseDurationSeconds"] = duration
    return keys


def merge_overlay(row: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    return {**row, **overlay} if overlay else row


async def _latest_keys_for_scope(
    exporter: ResponsesExporter,
    *,
    project_endpoint: str,
    project_id: str,
    agent_id: str | None,
    cutoff: datetime | None,
) -> dict[str, dict[str, Any]]:
    params = RESPONSE_INCREMENTAL.merge_params({}, cutoff)
    pages = (
        exporter._iter_agent_resource(  # noqa: SLF001
            project_endpoint=project_endpoint,
            project_id=project_id,
            agent_id=agent_id,
            params=params,
            cutoff=cutoff,
        )
        if agent_id
        else exporter._iter_project_scoped(  # noqa: SLF001
            project_endpoint=project_endpoint,
            project_id=project_id,
            params=params,
            cutoff=cutoff,
        )
    )
    latest: dict[str, Response] = {}
    async for page in pages:
        for item in page:
            try:
                row = Response.model_validate(item)
            except ValidationError:
                continue
            conversation_id = row.resolved_conversation_id()
            if not conversation_id:
                continue
            prev = latest.get(conversation_id)
            created, prev_created = row.created_at_datetime(), (
                prev.created_at_datetime() if prev else None
            )
            if prev is None or (
                created is not None
                and (prev_created is None or created >= prev_created)
            ):
                latest[conversation_id] = row
    return {
        conversation_id: conversation_latest_keys(response)
        for conversation_id, response in latest.items()
    }


async def enrich_conversation_pages(
    client: FoundryHttpClient,
    *,
    since_days: int,
    pages: AsyncIterator[list[dict[str, Any]]],
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    cutoff = effective_conversation_cutoff(
        active_incremental_cursor(), since_days=since_days
    )
    cache: dict[tuple[str, str, str | None], dict[str, dict[str, Any]]] = {}
    exporter = ResponsesExporter(client)
    async for page in pages:
        if not page:
            yield page
            continue
        sample = page[0]
        ep = str(sample.get("__foundryProjectEndpoint") or "")
        pid = str(sample.get("__foundryProjectId") or sample.get("__foundryProjectName") or "")
        agent_id = sample.get("__foundryAgentId")
        agent_key = str(agent_id).strip() if agent_id else None
        key = (ep, pid, agent_key)
        if key not in cache:
            cache[key] = await _latest_keys_for_scope(
                exporter,
                project_endpoint=ep,
                project_id=pid,
                agent_id=agent_key,
                cutoff=cutoff,
            )
        by_conv = cache[key]
        yield [
            merge_overlay(item, by_conv.get(str(item.get("id")), {})) for item in page
        ]
