from dataclasses import dataclass
from typing import Dict, Any, List, Type

from aws.core.exporters.codepipeline.utils.base_pipeline_action import PipelineAction
from aws.core.interfaces.action import Action, ActionMap, BaseActionInput
from loguru import logger
import asyncio


@dataclass
class GetPipelineStagesInput(BaseActionInput[dict[str, Any]]):
    region: str
    account_id: str


class GetPipelineStagesAction(PipelineAction[GetPipelineStagesInput]):
    """Fetches pipeline details and expands them into individual stage records.

    Takes a list of pipeline names and returns a flat list of stage records,
    one entry per stage across all pipelines.
    """

    async def _execute(self, resources: GetPipelineStagesInput) -> List[Dict[str, Any]]:
        pipeline_results = await asyncio.gather(
            *(
                self._fetch_pipeline_stages(
                    pipeline["name"],
                    region=resources.region,
                    account_id=resources.account_id,
                )
                for pipeline in resources.items
            ),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, result in enumerate(pipeline_results):
            if isinstance(result, list):
                results.extend(result)
            else:
                logger.warning(
                    f"Skipping stages for pipeline '{resources.items[idx]['name']}': {result}"
                )

        return results

    async def _fetch_pipeline_stages(
        self, pipeline_name: str, region: str, account_id: str
    ) -> List[Dict[str, Any]]:
        response = await self._get_pipeline(
            name=pipeline_name, cache_keys={"region": region, "account_id": account_id}
        )

        stage_records = []
        for order, stage in enumerate(
            response.get("pipeline", {}).get("stages", []), start=1
        ):
            stage_records.append(
                {
                    **stage,
                    "pipelineName": pipeline_name,
                    "pipelineArn": response.get("metadata", {}).get("pipelineArn", ""),
                    "order": order,
                }
            )

        logger.info(
            f"Fetched {len(stage_records)} stages for pipeline '{pipeline_name}'"
        )
        return stage_records


class CodePipelineStageActionsMap(ActionMap[GetPipelineStagesInput]):
    """Groups all actions for CodePipeline Stage resource type."""

    defaults: List[Type[Action[GetPipelineStagesInput]]] = [
        GetPipelineStagesAction,
    ]
    options: List[Type[Action[GetPipelineStagesInput]]] = []
