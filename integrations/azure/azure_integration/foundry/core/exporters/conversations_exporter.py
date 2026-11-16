from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger
from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.foundry.clients.http.foundry_client import FoundryApiError
from azure_integration.foundry.core.exporters.agents_exporter import AgentsExporter
from azure_integration.foundry.core.exporters.base import FoundryExporter
from azure_integration.foundry.core.options import ListConversationsOptions
from azure_integration.foundry.foundry_incremental import CONVERSATION_INCREMENTAL
from azure_integration.foundry.helpers.utils import (
    agent_openai_protocol_path,
    effective_conversation_cutoff,
    enrich_with_project,
)


class ConversationsExporter(FoundryExporter):
    """Conversations via agent protocol and/or project openai/v1 list APIs."""

    async def get_paginated_resources(
        self, options: ListConversationsOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        project_endpoint = options.project_endpoint
        project_id = options.project_id
        since_days = options.since_days
        scopes = options.endpoint_scopes
        incremental_cursor = active_incremental_cursor()
        cutoff = effective_conversation_cutoff(
            incremental_cursor, since_days=since_days
        )
        params = CONVERSATION_INCREMENTAL.merge_params({}, cutoff)

        scope_iters = {
            "agent": self._iter_agent_scoped_conversations,
            "project": self._iter_project_conversations,
        }
        for scope in scopes:
            iter_fn = scope_iters.get(scope)
            if not iter_fn:
                continue
            async for page in iter_fn(
                project_endpoint=project_endpoint,
                project_id=project_id,
                params=params,
                cutoff=cutoff,
            ):
                if page:
                    yield page

    async def _iter_agent_scoped_conversations(
        self,
        *,
        project_endpoint: str,
        project_id: str,
        params: dict[str, Any],
        cutoff: datetime | None,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        agents = AgentsExporter(self.client)
        async for agents_page in agents._iter_agent_pages(project_endpoint):
            for agent in agents_page:
                agent_id = agent.get("id")
                if not agent_id:
                    logger.warning(
                        "Skipping Foundry agent missing required id field",
                        agent=agent,
                        project_endpoint=project_endpoint,
                    )
                    continue
                async for page in self._iter_agent_conversations(
                    project_endpoint=project_endpoint,
                    project_id=project_id,
                    agent_id=str(agent_id),
                    params=params,
                    cutoff=cutoff,
                ):
                    yield page

    async def _iter_agent_conversations(
        self,
        *,
        project_endpoint: str,
        project_id: str,
        agent_id: str,
        params: dict[str, Any],
        cutoff: datetime | None,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        path = agent_openai_protocol_path(agent_id, "conversations")
        try:
            async for page in paginate_with_strategy(
                self.client.send_cursor_paginated_request(
                    project_endpoint,
                    path,
                    params=params,
                ),
                cursor=cutoff,
                strategy=CONVERSATION_INCREMENTAL,
            ):
                yield [
                    enrich_with_project(
                        {**item, "__foundryAgentId": agent_id},
                        project_endpoint=project_endpoint,
                        project_id=project_id,
                    )
                    for item in page
                    if item.get("id")
                ]
        except FoundryApiError as exc:
            # Agents without Conversations protocol can 4xx; skip, keep sync going.
            logger.warning(
                f"Skipping Foundry conversations for agent {agent_id} "
                f"({project_endpoint}): {exc}"
            )

    async def _iter_project_conversations(
        self,
        *,
        project_endpoint: str,
        project_id: str,
        params: dict[str, Any],
        cutoff: datetime | None,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for page in paginate_with_strategy(
            self.client.send_cursor_paginated_request(
                project_endpoint,
                "openai/v1/conversations",
                params=params,
            ),
            cursor=cutoff,
            strategy=CONVERSATION_INCREMENTAL,
        ):
            yield [
                enrich_with_project(
                    item,
                    project_endpoint=project_endpoint,
                    project_id=project_id,
                )
                for item in page
                if item.get("id")
            ]
