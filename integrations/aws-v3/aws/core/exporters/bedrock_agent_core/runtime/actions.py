import asyncio
from typing import Any, Type, cast

from loguru import logger

from aws.core.exporters.bedrock_agent_core.runtime.models import AgentRuntimeRecord
from aws.core.helpers.utils import is_recoverable_aws_exception
from aws.core.interfaces.action import Action, ActionMap


class ListAgentRuntimesAction(Action[list[AgentRuntimeRecord]]):
    """Pass-through action that wraps raw list_agent_runtimes items."""

    async def _execute(
        self, runtimes: list[AgentRuntimeRecord]
    ) -> list[dict[str, Any]]:
        return [dict(runtime) for runtime in runtimes]


class GetAgentRuntimeAction(Action[list[AgentRuntimeRecord]]):
    """Fetches full details for each BedrockAgentCore Runtime."""

    async def _execute(
        self, runtimes: list[AgentRuntimeRecord]
    ) -> list[dict[str, Any]]:
        details = await asyncio.gather(
            *(self._fetch_runtime_details(runtime) for runtime in runtimes),
            return_exceptions=True,
        )

        results: list[dict[str, Any]] = []
        for idx, detail_result in enumerate(details):
            if isinstance(detail_result, Exception):
                runtime_id = runtimes[idx].get("agentRuntimeId", "unknown")
                if is_recoverable_aws_exception(detail_result):
                    logger.warning(
                        f"Skipping BedrockAgentCore Runtime '{runtime_id}': {detail_result}"
                    )
                    results.append({})
                    continue
                else:
                    logger.error(
                        f"Error fetching details for BedrockAgentCore Runtime '{runtime_id}': {detail_result}"
                    )
                    raise detail_result
            results.append(cast(dict[str, Any], detail_result))
        logger.info(
            f"Successfully fetched details for {len(results)} BedrockAgentCore Runtimes"
        )
        return results

    async def _fetch_runtime_details(
        self, runtime: AgentRuntimeRecord
    ) -> dict[str, Any]:
        runtime_id = runtime["agentRuntimeId"]
        response = await self.client.get_agent_runtime(agentRuntimeId=runtime_id)
        response.pop("ResponseMetadata", None)
        logger.info(
            f"Successfully fetched details for BedrockAgentCore Runtime '{runtime_id}'"
        )
        return response


class BedrockAgentCoreRuntimeActionsMap(ActionMap[list[AgentRuntimeRecord]]):
    """Groups all actions for BedrockAgentCore Runtimes."""

    defaults: list[Type[Action[list[AgentRuntimeRecord]]]] = [
        ListAgentRuntimesAction,
        GetAgentRuntimeAction,
    ]
    options: list[Type[Action[list[AgentRuntimeRecord]]]] = []
