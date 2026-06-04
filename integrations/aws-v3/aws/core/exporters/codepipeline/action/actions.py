from typing import Any, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import is_recoverable_aws_exception
from loguru import logger
import asyncio


class GetPipelineActionsDetails(Action):
    """Fetches pipeline details to extract action information."""

    async def _execute(self, pipeline_names: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not pipeline_names:
            return []

        pipeline_actions = await asyncio.gather(
            *(self._fetch_pipeline_actions(pipeline_name['name']) for pipeline_name in pipeline_names),
            return_exceptions=True,
        )

        actions = [action for sublist in pipeline_actions for action in sublist]

        logger.info(f"Successfully extracted {len(actions)} CodePipeline actions")
        return actions

    async def _fetch_pipeline_actions(self, pipeline_name: str) -> list[dict[str, Any]]:
        pipeline_data = await self.client.get_pipeline(name=pipeline_name)
        logger.info(f"Successfully fetched pipeline details for {pipeline_name}")

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
                action_type_data = action.get('actionTypeId')
                actions.append({
                    "ActionName": action.get("name", ""),
                    "ActionTypeId": {
                        'Category': action_type_data.get('category'),
                        'Owner': action_type_data.get('owner'),
                        'Provider': action_type_data.get('provider'),
                        'Version': action_type_data.get('version'),
                    } if action_type_data else {},
                    "RunOrder": action.get("runOrder"),
                    "Configuration": action.get("configuration", {}),
                    "InputArtifacts": action.get("inputArtifacts", []),
                    "OutputArtifacts": action.get("outputArtifacts", []),
                    "RoleArn": action.get("roleArn"),
                    "Region": action.get("region"),
                    "Namespace": action.get("namespace"),
                    "TimeoutInMinutes": action.get("timeoutInMinutes"),
                    "OnFailure": action.get("onFailure"),
                    "PipelineName": pipeline_name,
                    "StageName": stage_name,
                    "PipelineArn": pipeline_arn,
                    "PipelineVersion": pipeline_version,
                })

        return actions


class CodePipelineActionActionsMap(ActionMap):
    """Groups all actions for CodePipeline actions."""

    defaults: list[Type[Action]] = [
        GetPipelineActionsDetails,
    ]
    options: list[Type[Action]] = []
