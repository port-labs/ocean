from dataclasses import dataclass
from typing import Any, Type, cast, Dict, List
from aws.core.interfaces.action import Action, ActionMap, BaseActionInput
from aws.core.helpers.utils import is_recoverable_aws_exception
from loguru import logger
import asyncio


@dataclass
class CodePipelineExecutionActionInput(BaseActionInput[dict[str, Any]]):
    pipeline_name: str


class ListPipelineExecutionsAction(Action[CodePipelineExecutionActionInput]):
    """Processes the initial list of pipeline executions."""

    async def _execute(self, resources: CodePipelineExecutionActionInput) -> list[dict[str, Any]]:
        return resources.items


class GetPipelineExecutionDetailsAction(Action[CodePipelineExecutionActionInput]):
    """Fetches detailed information about pipeline executions."""

    async def _execute(self, resources: CodePipelineExecutionActionInput) -> list[dict[str, Any]]:
        details = await asyncio.gather(
            *(self._fetch_pipeline_execution_details(pipeline_name=resources.pipeline_name,
                                                     execution=execution) for execution in resources.items),
            return_exceptions=True,
        )

        results: list[dict[str, Any]] = []
        for idx, detail_result in enumerate(details):
            if isinstance(detail_result, Exception):
                execution_id = resources.items[idx].get("pipelineExecutionId", "unknown")
                logger.warning(
                    f"Skipping pipeline execution details for pipeline '{resources.pipeline_name}' execution '{execution_id}': {detail_result}"
                )
                results.append({})
            else:
                results.append(cast(dict[str, Any], detail_result))

        logger.info(f"Successfully fetched details for {len(results)} pipeline executions")
        return results

    async def _fetch_pipeline_execution_details(self, pipeline_name: str, execution: dict[str, Any]) -> dict[str, Any]:
        response = await self.client.get_pipeline_execution(
            pipelineName=pipeline_name,
            pipelineExecutionId=execution['pipelineExecutionId']
        )

        logger.info(f"Successfully fetched details for pipeline '{pipeline_name}' execution '{execution['pipelineExecutionId']}'")
        return response["pipelineExecution"]


class CodePipelinePipelineExecutionActionsMap(ActionMap):
    """Groups all actions for CodePipeline pipeline executions."""

    defaults: list[Type[Action]] = [
        ListPipelineExecutionsAction,
        GetPipelineExecutionDetailsAction,
    ]
    options: list[Type[Action]] = []
