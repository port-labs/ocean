from dataclasses import dataclass
from typing import Any, List, Type

from aws.core.interfaces.action import Action, ActionMap, BaseActionInput
from loguru import logger
import asyncio


@dataclass
class CodePipelineActionExecutionInput(BaseActionInput[dict[str, Any]]):
    region: str
    account_id: str


class GetActionExecutionsAction(Action[CodePipelineActionExecutionInput]):
    """Fetches action executions for all pipelines in the region."""

    async def _execute(
        self, identifiers: CodePipelineActionExecutionInput
    ) -> list[dict[str, Any]]:
        pipeline_executions = await asyncio.gather(
            *(
                self._fetch_pipeline_action_executions(
                    pipeline["name"],
                    region=identifiers.region,
                    account_id=identifiers.account_id,
                )
                for pipeline in identifiers.items
            ),
            return_exceptions=True,
        )

        results: list[dict[str, Any]] = []
        for idx, result in enumerate(pipeline_executions):
            if isinstance(result, list):
                results.extend(result)
            else:
                pipeline_name = identifiers.items[idx].get("name", "unknown")
                logger.error(
                    f"Error fetching action executions for pipeline '{pipeline_name}': {result}"
                )

        logger.info(
            f"Successfully fetched {len(results)} CodePipeline action executions"
        )
        return results

    async def _fetch_pipeline_action_executions(
        self, pipeline_name: str, region: str, account_id: str
    ) -> list[dict[str, Any]]:
        paginator = self.client.get_paginator("list_action_executions")
        action_executions: list[dict[str, Any]] = []

        async for page in paginator.paginate(pipelineName=pipeline_name):
            for execution in page.get("actionExecutionDetails", []):
                action_executions.append(
                    {
                        **execution,
                        "pipelineName": pipeline_name,
                    }
                )

        logger.info(
            f"Successfully fetched {len(action_executions)} action executions for pipeline '{pipeline_name}'"
        )
        return action_executions


class CodePipelineActionExecutionActionsMap(ActionMap[CodePipelineActionExecutionInput]):
    """Groups all actions for CodePipeline action executions."""

    defaults: List[Type[Action[CodePipelineActionExecutionInput]]] = [
        GetActionExecutionsAction,
    ]
    options: List[Type[Action[CodePipelineActionExecutionInput]]] = []
