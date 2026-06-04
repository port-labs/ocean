from typing import Any, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import is_recoverable_aws_exception
from loguru import logger
import asyncio


class GetPipelineDetailsAction(Action):
    """Fetches pipeline details to extract action information."""

    async def _execute(self, pipeline_names: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not pipeline_names:
            return []

        pipeline_details = await asyncio.gather(
            *(self._fetch_pipeline_details(pipeline_name['name']) for pipeline_name in pipeline_names),
            return_exceptions=True,
        )

        results: list[dict[str, Any]] = []
        for idx, details_result in enumerate(pipeline_details):
            if isinstance(details_result, Exception):
                pipeline_name = pipeline_names[idx]
                if is_recoverable_aws_exception(details_result):
                    logger.warning(
                        f"Skipping pipeline details for pipeline '{pipeline_name}': {details_result}"
                    )
                    continue
                else:
                    logger.error(
                        f"Error fetching pipeline details for pipeline '{pipeline_name}': {details_result}"
                    )
                    raise details_result

            # Extract actions from pipeline details
            pipeline_data = cast(dict[str, Any], details_result)
            actions = self._extract_actions_from_pipeline(pipeline_data)
            results.extend(actions)

        logger.info(f"Successfully extracted {len(results)} CodePipeline actions")
        return results

    async def _fetch_pipeline_details(self, pipeline_name: str) -> dict[str, Any]:
        """Fetch pipeline details from AWS."""
        response = await self.client.get_pipeline(name=pipeline_name)
        logger.info(f"Successfully fetched pipeline details for {pipeline_name}")
        return response

    def _extract_actions_from_pipeline(self, pipeline_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract individual actions from pipeline structure."""
        actions = []
        pipeline_info = pipeline_data.get("pipeline", {})
        pipeline_name = pipeline_info.get("name", "")
        pipeline_arn = pipeline_info.get("roleArn", "")
        pipeline_version = pipeline_info.get("version", 0)

        stages = pipeline_info.get("stages", [])
        for stage in stages:
            stage_name = stage.get("name", "")
            stage_actions = stage.get("actions", [])

            for action in stage_actions:
                action_data = {
                    "ActionName": action.get("name", ""),
                    "ActionTypeId": action.get("actionTypeId", {}),
                    "RunOrder": action.get("runOrder"),
                    "Configuration": action.get("configuration", {}),
                    "InputArtifacts": action.get("inputArtifacts", []),
                    "OutputArtifacts": action.get("outputArtifacts", []),
                    "RoleArn": action.get("roleArn"),
                    "Region": action.get("region"),
                    "Namespace": action.get("namespace"),
                    "TimeoutInMinutes": action.get("timeoutInMinutes"),
                    "OnFailure": action.get("onFailure"),
                    # Add pipeline context
                    "PipelineName": pipeline_name,
                    "StageName": stage_name,
                    "PipelineArn": pipeline_arn,
                    "PipelineVersion": pipeline_version,
                }
                actions.append(action_data)

        return actions


class CodePipelineActionActionsMap(ActionMap):
    """Groups all actions for CodePipeline actions."""

    defaults: list[Type[Action]] = [
        GetPipelineDetailsAction,
    ]
    options: list[Type[Action]] = []
