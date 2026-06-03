from typing import Dict, Any, List, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger
import asyncio


class ListPipelineAction(Action):
    """Lists all CodePipeline pipelines to iterate through for action executions."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fetch all pipelines to search for action executions."""
        try:
            response = await self.client.list_pipelines()
            pipelines = response.get("pipelines", [])
            
            results: List[Dict[str, Any]] = []
            for pipeline in pipelines:
                pipeline_data = {
                    "pipeline_name": pipeline.get("name", ""),
                    "version": pipeline.get("version", 1),
                    "created": pipeline.get("created"),
                    "updated": pipeline.get("updated"),
                }
                results.append(pipeline_data)
            
            logger.info(f"Found {len(results)} CodePipeline pipelines")
            return results
        except Exception as e:
            logger.error(f"Error listing CodePipeline pipelines: {e}")
            raise


class GetPipelineExecutionAction(Action):
    """Fetches pipeline executions for each pipeline."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not resources:
            return []

        # Use asyncio.gather for concurrent API calls
        executions = await asyncio.gather(
            *(self._fetch_pipeline_executions(resource) for resource in resources),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, execution_result in enumerate(executions):
            if isinstance(execution_result, Exception):
                pipeline_name = resources[idx].get("pipeline_name", "unknown")
                logger.error(f"Error fetching executions for pipeline '{pipeline_name}': {execution_result}")
                continue
            results.extend(cast(List[Dict[str, Any]], execution_result))
        return results

    async def _fetch_pipeline_executions(self, resource: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch pipeline executions for a specific pipeline."""
        pipeline_name = resource.get("pipeline_name")
        if not pipeline_name:
            return []

        try:
            response = await self.client.list_pipeline_executions(
                pipelineName=pipeline_name,
                maxResults=50  # Reasonable limit to avoid too much data
            )
            
            executions = response.get("pipelineExecutionSummaries", [])
            results: List[Dict[str, Any]] = []
            
            for execution in executions:
                execution_data = {
                    "pipeline_name": pipeline_name,
                    "pipeline_execution_id": execution.get("pipelineExecutionId", ""),
                    "status": execution.get("status", ""),
                    "start_time": execution.get("startTime"),
                    "last_update_time": execution.get("lastUpdateTime"),
                    "source_revisions": execution.get("sourceRevisions", []),
                    "trigger": execution.get("trigger", {}),
                }
                results.append(execution_data)
            
            logger.info(f"Found {len(results)} executions for pipeline {pipeline_name}")
            return results
            
        except self.client.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "PipelineNotFoundException":
                logger.info(f"Pipeline not found: {pipeline_name}")
                return []
            else:
                logger.error(f"Error fetching executions for pipeline {pipeline_name}: {e}")
                raise


class GetActionExecutionAction(Action):
    """Fetches action executions for each pipeline execution."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not resources:
            return []

        # Use asyncio.gather for concurrent API calls
        action_executions = await asyncio.gather(
            *(self._fetch_action_executions(resource) for resource in resources),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, action_execution_result in enumerate(action_executions):
            if isinstance(action_execution_result, Exception):
                pipeline_name = resources[idx].get("pipeline_name", "unknown")
                execution_id = resources[idx].get("pipeline_execution_id", "unknown")
                logger.error(f"Error fetching action executions for pipeline '{pipeline_name}' execution '{execution_id}': {action_execution_result}")
                continue
            results.extend(cast(List[Dict[str, Any]], action_execution_result))
        return results

    async def _fetch_action_executions(self, resource: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch action executions for a specific pipeline execution."""
        pipeline_name = resource.get("pipeline_name")
        pipeline_execution_id = resource.get("pipeline_execution_id")
        
        if not pipeline_name or not pipeline_execution_id:
            return []

        try:
            response = await self.client.list_action_executions(
                pipelineName=pipeline_name,
                filter={
                    "pipelineExecutionId": pipeline_execution_id
                }
            )
            
            action_executions = response.get("actionExecutionDetails", [])
            results: List[Dict[str, Any]] = []
            
            for action_execution in action_executions:
                action_execution_data = {
                    "PipelineName": pipeline_name,
                    "PipelineExecutionId": pipeline_execution_id,
                    "ActionExecutionId": action_execution.get("actionExecutionId", ""),
                    "ActionName": action_execution.get("actionName", ""),
                    "StageName": action_execution.get("stageName", ""),
                    "Status": action_execution.get("status", ""),
                    "StartTime": action_execution.get("startTime"),
                    "LastUpdateTime": action_execution.get("lastUpdateTime"),
                    "Input": action_execution.get("input", {}),
                    "Output": action_execution.get("output", {}),
                    "ErrorDetails": action_execution.get("errorDetails", {}),
                    "ExternalExecutionId": action_execution.get("externalExecutionId"),
                    "ExternalExecutionUrl": action_execution.get("externalExecutionUrl"),
                    "PercentComplete": action_execution.get("percentComplete"),
                    "Summary": action_execution.get("summary"),
                    "ActionTypeId": action_execution.get("actionTypeId", {}),
                    # Add extra context
                    "Region": resource.get("region"),
                    "AccountId": resource.get("account_id"),
                }
                results.append(action_execution_data)
            
            logger.info(f"Found {len(results)} action executions for pipeline {pipeline_name} execution {pipeline_execution_id}")
            return results
            
        except self.client.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "PipelineExecutionNotFoundException":
                logger.info(f"Pipeline execution not found: {pipeline_execution_id}")
                return []
            else:
                logger.error(f"Error fetching action executions for pipeline {pipeline_name} execution {pipeline_execution_id}: {e}")
                raise


class ActionExecutionActionsMap(ActionMap):
    """Groups all actions for CodePipeline ActionExecution resource type."""
    
    defaults: List[Type[Action]] = [
        ListPipelineAction,
        GetPipelineExecutionAction,
        GetActionExecutionAction,
    ]
    options: List[Type[Action]] = []