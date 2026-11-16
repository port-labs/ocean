from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, ClassVar

from loguru import logger
from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import (
    IncrementalStrategy,
    paginate_with_strategy,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_independent_async_iterators,
)

from azure_integration.foundry.clients.http.foundry_client import FoundryApiError
from azure_integration.foundry.core.exporters.agents_exporter import AgentsExporter
from azure_integration.foundry.core.exporters.base import FoundryExporter
from azure_integration.foundry.core.options import (
    EndpointScope,
    ListConversationsOptions,
    ListResponsesOptions,
)
from azure_integration.foundry.helpers.utils import (
    agent_openai_protocol_path,
    effective_conversation_cutoff,
    enrich_with_project,
)

EndpointScopedOptions = ListConversationsOptions | ListResponsesOptions
MAX_CONCURRENT_AGENTS = 10


class EndpointScopedExporter(FoundryExporter):
    """Lists a Foundry resource via agent protocol and/or project openai/v1 APIs."""

    resource: ClassVar[str]
    strategy: ClassVar[IncrementalStrategy]

    async def get_paginated_resources(
        self, options: EndpointScopedOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        project_endpoint = options.project_endpoint
        project_id = options.project_id
        cutoff = effective_conversation_cutoff(
            active_incremental_cursor(), since_days=options.since_days
        )
        params = self.strategy.merge_params({}, cutoff)

        scope_iters = {
            EndpointScope.AGENT: self._iter_agent_scoped,
            EndpointScope.PROJECT: self._iter_project_scoped,
        }
        for scope in options.endpoint_scopes:
            async for page in scope_iters[scope](
                project_endpoint=project_endpoint,
                project_id=project_id,
                params=params,
                cutoff=cutoff,
            ):
                if page:
                    yield page

    async def _iter_agent_scoped(
        self,
        *,
        project_endpoint: str,
        project_id: str,
        params: dict[str, Any],
        cutoff: datetime | None,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        agents = AgentsExporter(self.client)
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_AGENTS)
        context = f"Foundry {self.resource}"

        async for agents_page in agents.iter_agent_pages(project_endpoint):
            tasks = []
            for agent in agents_page:
                agent_id = agent.get("id")
                if not agent_id:
                    logger.warning(
                        "Skipping Foundry agent missing required id field",
                        agent=agent,
                        project_endpoint=project_endpoint,
                    )
                    continue

                def build_iterator(
                    agent_id: str = str(agent_id),
                ) -> ASYNC_GENERATOR_RESYNC_TYPE:
                    return self._iter_agent_resource(
                        project_endpoint=project_endpoint,
                        project_id=project_id,
                        agent_id=agent_id,
                        params=params,
                        cutoff=cutoff,
                    )

                tasks.append(semaphore_async_iterator(semaphore, build_iterator))

            if not tasks:
                continue

            async for page in stream_independent_async_iterators(
                *tasks, context=context
            ):
                if page:
                    yield page

    async def _iter_agent_resource(
        self,
        *,
        project_endpoint: str,
        project_id: str,
        agent_id: str,
        params: dict[str, Any],
        cutoff: datetime | None,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        path = agent_openai_protocol_path(agent_id, self.resource)
        try:
            async for page in paginate_with_strategy(
                self.client.send_cursor_paginated_request(
                    project_endpoint,
                    path,
                    params=params,
                ),
                cursor=cutoff,
                strategy=self.strategy,
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
            if not exc.is_skippable_client_error:
                raise
            # Agents without this protocol can 4xx; skip, keep sync going.
            logger.warning(
                f"Skipping Foundry {self.resource} for agent {agent_id} "
                f"({project_endpoint}): {exc}"
            )

    async def _iter_project_scoped(
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
                f"openai/v1/{self.resource}",
                params=params,
            ),
            cursor=cutoff,
            strategy=self.strategy,
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
