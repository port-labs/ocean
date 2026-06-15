from dataclasses import dataclass
from typing import Any, Type

from aws.core.exporters.codepipeline.utils.base_pipeline_action import PipelineAction
from aws.core.interfaces.action import Action, ActionMap, BaseActionInput
from loguru import logger
import asyncio


@dataclass
class CodePipelinePipelineActionInput(BaseActionInput[dict[str, Any]]):
    region: str
    account_id: str


class GetPipelineActionsDetails(PipelineAction[CodePipelinePipelineActionInput]):
    """Fetches pipeline details to extract action information."""

    async def _execute(self, identifiers: CodePipelinePipelineActionInput) -> list[dict[str, Any]]:
        pipeline_actions = await asyncio.gather(
            *(self._fetch_pipeline_actions(pipeline['name'], region=identifiers.region, account_id=identifiers.account_id) for pipeline in identifiers.items),
            return_exceptions=True,
        )

        results: list[dict[str, Any]] = []
        for idx, detail_result in enumerate(pipeline_actions):
            if isinstance(detail_result, list):
                results.extend(detail_result)
            else:
                pipeline_name = identifiers.items[idx].get("name", "unknown")
                logger.error(
                    f"Error fetching details for pipeline '{pipeline_name}': {detail_result}"
                )
                results.append({})

        logger.info(f"Successfully extracted {len(results)} CodePipeline actions")
        return results

    async def _fetch_pipeline_actions(self, pipeline_name: str, region: str, account_id: str) -> list[dict[str, Any]]:
        pipeline_data = await self._get_pipeline(pipeline_name, cache_keys={'region': region, 'account_id': account_id})
        logger.info(f"Successfully fetched pipeline details for {pipeline_name}")

        actions = []
        pipeline_arn = pipeline_data.get('metadata', {}).get("pipelineArn", "")
        pipeline_info = pipeline_data.get("pipeline", {})
        pipeline_name = pipeline_info.get("name", "")
        pipeline_version = pipeline_info.get("version", 0)
        stages = pipeline_info.get("stages", [])

        for stage in stages:
            stage_name = stage.get("name", "")

            for action in stage.get("actions", []):
                actions.append({
                    **action,
                    'pipelineName': pipeline_name,
                    'pipelineArn': pipeline_arn,
                    'pipelineVersion': pipeline_version,
                    'stageName': stage_name,
                })

        return actions


class CodePipelineActionActionsMap(ActionMap[CodePipelinePipelineActionInput]):
    """Groups all actions for CodePipeline actions."""

    defaults: list[Type[Action[CodePipelinePipelineActionInput]]] = [
        GetPipelineActionsDetails,
    ]
    options: list[Type[Action[CodePipelinePipelineActionInput]]] = []
