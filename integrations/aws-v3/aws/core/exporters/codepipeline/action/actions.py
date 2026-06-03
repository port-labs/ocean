from typing import Any, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import is_recoverable_aws_exception
from loguru import logger
import asyncio


class GetPipelineDetailsAction(Action):
    """Fetches pipeline details to extract action information."""

    async def _execute(self, pipeline_names: list[str]) -> list[dict[str, Any]]:
        if not pipeline_names:
            return []

        pipeline_details = await asyncio.gather(
            *(self._fetch_pipeline_details(pipeline_name) for pipeline_name in pipeline_names),
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


class ListPipelinesAction(Action):
    """Lists all pipelines to discover actions."""

    async def _execute(self, pipeline_list: list[dict[str, Any]]) -> list[str]:
        """Extract pipeline names from the pipeline list."""
        pipeline_names = []
        for pipeline_item in pipeline_list:
            if isinstance(pipeline_item, dict) and "name" in pipeline_item:
                pipeline_names.append(pipeline_item["name"])
            elif isinstance(pipeline_item, str):
                pipeline_names.append(pipeline_item)
        
        logger.info(f"Found {len(pipeline_names)} pipelines to process")
        return pipeline_names


class GetPipelineExecutionDetailsAction(Action):
    """Optional action to fetch execution details for actions."""

    async def _execute(self, actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not actions:
            return []

        # Group actions by pipeline for efficient API calls
        pipelines_actions = {}
        for action in actions:
            pipeline_name = action.get("PipelineName", "")
            if pipeline_name not in pipelines_actions:
                pipelines_actions[pipeline_name] = []
            pipelines_actions[pipeline_name].append(action)

        enriched_actions = []
        for pipeline_name, pipeline_actions in pipelines_actions.items():
            try:
                # Get recent executions for context
                executions_response = await self.client.list_pipeline_executions(
                    pipelineName=pipeline_name,
                    maxResults=5
                )
                
                latest_execution = executions_response.get("pipelineExecutionSummaries", [])
                if latest_execution:
                    latest_execution_id = latest_execution[0].get("pipelineExecutionId", "")
                    
                    for action in pipeline_actions:
                        # Add execution context if available
                        action["LatestExecutionId"] = latest_execution_id
                        action["LatestExecutionStatus"] = latest_execution[0].get("status", "")
                        enriched_actions.append(action)
                else:
                    enriched_actions.extend(pipeline_actions)
                    
            except Exception as e:
                if is_recoverable_aws_exception(e):
                    logger.warning(f"Could not fetch execution details for pipeline '{pipeline_name}': {e}")
                    enriched_actions.extend(pipeline_actions)
                else:
                    logger.error(f"Error fetching execution details for pipeline '{pipeline_name}': {e}")
                    raise

        logger.info(f"Successfully enriched {len(enriched_actions)} actions with execution details")
        return enriched_actions


class CodePipelineActionActionsMap(ActionMap):
    """Groups all actions for CodePipeline actions."""

    defaults: list[Type[Action]] = [
        ListPipelinesAction,
        GetPipelineDetailsAction,
    ]
    options: list[Type[Action]] = [
        GetPipelineExecutionDetailsAction,
    ]