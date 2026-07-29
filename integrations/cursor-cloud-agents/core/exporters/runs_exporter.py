from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients.cursor_agents_client import CursorAgentsClient
from clients.endpoints import v1_agent_run, v1_agent_runs
from core.catalog import format_datetime_for_catalog
from core.exporters.abstract_exporter import AbstractCursorExporter
from core.exporters.agents_exporter import AgentsExporter
from core.options import GetRunOptions, ListRunOptions


def _parse_run_created_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


class RunsExporter(AbstractCursorExporter):
    """Syncs the `run` kind from the v1 List Runs API, one page of agents at a
    time (via v1 List Agents) fanned out into a List Runs call per agent.

    Sequential per-agent list calls, not concurrent: Cursor's Cloud Agents API
    doesn't expose a rate-limit budget to pace against (see
    `CursorAgentsClient`), so fanning out unboundedly risks tripping `429`s
    that Ocean's retry transport would then have to absorb across many
    in-flight requests at once.

    List/Get Run don't carry token usage inline - it's a separate `GET
    /v1/agents/{id}/usage` call, but one call returns usage for every run on
    the agent, so it's fetched once per agent (not once per run) and merged
    into each run dict before yielding."""

    def __init__(
        self,
        client: CursorAgentsClient,
        agents_exporter: AgentsExporter | None = None,
    ) -> None:
        super().__init__(client)
        self._agents_exporter = agents_exporter or AgentsExporter(client)

    async def list_first_page(self, agent_id: str) -> list[dict[str, Any]]:
        """First page of runs for an agent (newest first per Cursor API docs)."""
        payload = await self.client.send_api_request(
            "GET",
            v1_agent_runs(agent_id),
            params={"limit": self.client.page_size},
        )
        items = payload.get("items")
        if not isinstance(items, list):
            return []
        return items

    async def get_paginated_resources(
        self, options: ListRunOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        agent_options = options.to_agent_options()
        async for agents_batch in self._agents_exporter.get_paginated_resources(
            agent_options
        ):
            for agent in agents_batch:
                agent_id = agent.get("id")
                if not agent_id:
                    continue
                usage_by_run_id: dict[str, Any] = {}
                if options.enrich_runs_with_usage:
                    usage_by_run_id = (
                        await self._agents_exporter.get_runs_usage_map_for_agent(
                            agent_id
                        )
                    )
                async for runs_batch in self.client.paginate_by_cursor(
                    v1_agent_runs(agent_id), "items"
                ):
                    if not runs_batch:
                        continue
                    filtered_batch: list[dict[str, Any]] = []
                    stop_pagination = False
                    for run in runs_batch:
                        created_at = _parse_run_created_at(run.get("createdAt"))
                        if (
                            options.oldest_run_date is not None
                            and created_at is not None
                            and created_at < options.oldest_run_date
                        ):
                            stop_pagination = True
                            continue
                        run.setdefault("agentId", agent_id)
                        run_id = run.get("id")
                        usage = usage_by_run_id.get(run_id) if run_id else None
                        if usage is not None:
                            run["usage"] = usage
                        filtered_batch.append(run)
                    if filtered_batch:
                        logger.debug(
                            f"Fetched {len(filtered_batch)} run(s) for Cursor agent {agent_id}"
                        )
                        yield filtered_batch
                    if stop_pagination:
                        break

    async def get_resource(self, options: GetRunOptions) -> dict[str, Any]:
        async def fetch_run_or_fallback() -> dict[str, Any]:
            try:
                return dict(
                    await self.client.send_api_request(
                        "GET", v1_agent_run(options.agent_id, options.run_id)
                    )
                )
            except Exception as error:
                logger.warning(
                    f"Failed to fetch Cursor run {options.run_id} for agent "
                    f"{options.agent_id} (using webhook snapshot): {error}"
                )
                return {"id": options.run_id}

        run_raw, usage_by_run_id = await asyncio.gather(
            fetch_run_or_fallback(),
            self._agents_exporter.get_runs_usage_map_for_agent(options.agent_id),
        )
        run_raw.setdefault("agentId", options.agent_id)
        if options.status is not None:
            run_raw.setdefault("status", options.status)
        if options.updated_at is not None:
            run_raw.setdefault(
                "updatedAt", format_datetime_for_catalog(options.updated_at)
            )
        usage = usage_by_run_id.get(options.run_id)
        if usage is not None:
            run_raw["usage"] = usage
        return run_raw
