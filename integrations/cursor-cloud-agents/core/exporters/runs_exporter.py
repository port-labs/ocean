from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients.endpoints import V1_AGENTS, v1_agent_runs
from core.catalog import fetch_usage_by_run_id
from core.exporters.abstract_exporter import AbstractCursorExporter


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

    async def get_paginated_resources(
        self, *, include_archived: bool = False
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        query_params = {"includeArchived": include_archived}
        async for agents_batch in self.client.paginate_by_cursor(
            V1_AGENTS, "items", params=query_params
        ):
            for agent in agents_batch:
                agent_id = agent.get("id")
                if not agent_id:
                    continue
                usage_by_run_id = await fetch_usage_by_run_id(self.client, agent_id)
                async for runs_batch in self.client.paginate_by_cursor(
                    v1_agent_runs(agent_id), "items"
                ):
                    if not runs_batch:
                        continue
                    for run in runs_batch:
                        run_id = run.get("id")
                        usage = usage_by_run_id.get(run_id) if run_id else None
                        if usage is not None:
                            run["usage"] = usage
                    logger.debug(
                        f"Fetched {len(runs_batch)} run(s) for Cursor agent {agent_id}"
                    )
                    yield runs_batch
