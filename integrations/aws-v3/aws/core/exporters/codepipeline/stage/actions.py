from typing import Dict, Any, List, Type
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import is_recoverable_aws_exception
from loguru import logger
import asyncio


class GetPipelineStagesAction(Action[list[str]]):
    """Fetches pipeline details and expands them into individual stage records.

    Takes a list of pipeline names and returns a flat list of stage records,
    one entry per stage across all pipelines.
    """

    async def _execute(self, pipeline_names: list[str]) -> List[Dict[str, Any]]:
        if not pipeline_names:
            return []

        pipeline_results = await asyncio.gather(
            *(self._fetch_pipeline_stages(name) for name in pipeline_names),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        success_count = 0
        for idx, result in enumerate(pipeline_results):
            if isinstance(result, Exception):
                name = pipeline_names[idx]
                if is_recoverable_aws_exception(result):
                    logger.warning(
                        f"Skipping stages for pipeline '{name}': {result}"
                    )
                    continue
                else:
                    logger.error(
                        f"Error fetching stages for pipeline '{name}': {result}"
                    )
                    raise result
            results.extend(result)  # type: ignore[arg-type]
            success_count += 1

        logger.info(
            f"Successfully fetched stages for {success_count} CodePipeline pipelines"
        )
        return results

    async def _fetch_pipeline_stages(
        self, pipeline_name: str
    ) -> List[Dict[str, Any]]:
        response = await self.client.get_pipeline(name=pipeline_name)
        pipeline = response.get("pipeline", {})
        metadata = response.get("metadata", {})

        pipeline_arn = metadata.get("pipelineArn", "")
        stages: List[Dict[str, Any]] = pipeline.get("stages", [])

        stage_records: List[Dict[str, Any]] = []
        for order, stage in enumerate(stages, start=1):
            stage_records.append(
                {
                    **stage,
                    "pipelineName": pipeline_name,
                    "pipelineArn": pipeline_arn,
                    "order": order,
                }
            )

        logger.info(
            f"Fetched {len(stage_records)} stages for pipeline '{pipeline_name}'"
        )
        return stage_records


class CodePipelineStageActionsMap(ActionMap[list[str]]):
    """Groups all actions for CodePipeline Stage resource type."""

    defaults: List[Type[Action[list[str]]]] = [
        GetPipelineStagesAction,
    ]
    options: List[Type[Action[list[str]]]] = []
