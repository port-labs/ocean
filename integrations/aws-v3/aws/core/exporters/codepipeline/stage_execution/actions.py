from typing import Dict, Any, List, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger
import asyncio


class ListPipelinesAction(Action):
    """Fetches all CodePipelines to get pipeline executions."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """List all pipelines in the region."""
        try:
            response = await self.client.list_pipelines()
            pipelines = response.get("pipelines", [])
            
            logger.info(f"Found {len(pipelines)} pipelines")
            
            results: List[Dict[str, Any]] = []
            for pipeline in pipelines:
                results.append({
                    "pipelineName": pipeline.get("name", ""),
                    "version": pipeline.get("version"),
                    "created": pipeline.get("created"),
                    "updated": pipeline.get("updated"),
                })
            
            return results
        except Exception as e:
            logger.error(f"Error listing pipelines: {e}")
            return []


class GetPipelineExecutionsAction(Action):
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
                pipeline_name = resources[idx].get("pipelineName", "unknown")
                logger.error(f"Error fetching executions for pipeline '{pipeline_name}': {execution_result}")
                continue
            results.extend(cast(List[Dict[str, Any]], execution_result))
        
        return results

    async def _fetch_pipeline_executions(self, pipeline: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch executions for a specific pipeline."""
        pipeline_name = pipeline["pipelineName"]
        try:
            response = await self.client.list_pipeline_executions(pipelineName=pipeline_name)
            executions = response.get("pipelineExecutionSummaries", [])
            
            logger.info(f"Found {len(executions)} executions for pipeline {pipeline_name}")
            
            results: List[Dict[str, Any]] = []
            for execution in executions:
                results.append({
                    "pipelineName": pipeline_name,
                    "pipelineExecutionId": execution.get("pipelineExecutionId", ""),
                    "status": execution.get("status"),
                    "startTime": execution.get("startTime"),
                    "lastUpdateTime": execution.get("lastUpdateTime"),
                    "sourceRevisions": execution.get("sourceRevisions", []),
                    "trigger": execution.get("trigger", {}),
                })
            
            return results
        except self.client.exceptions.ClientError as e:
            if e.response.get("Error", {}).get("Code") == "PipelineNotFoundException":
                logger.info(f"Pipeline {pipeline_name} not found")
                return []
            else:
                logger.error(f"Error fetching executions for pipeline {pipeline_name}: {e}")
                raise


class GetStageExecutionsAction(Action):
    """Fetches stage execution details for pipeline executions."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not resources:
            return []

        # Use asyncio.gather for concurrent API calls
        stage_executions = await asyncio.gather(
            *(self._fetch_stage_executions(resource) for resource in resources),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, stage_execution_result in enumerate(stage_executions):
            if isinstance(stage_execution_result, Exception):
                execution_id = resources[idx].get("pipelineExecutionId", "unknown")
                logger.error(f"Error fetching stage executions for execution '{execution_id}': {stage_execution_result}")
                continue
            results.extend(cast(List[Dict[str, Any]], stage_execution_result))
        
        return results

    async def _fetch_stage_executions(self, execution: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch stage executions for a specific pipeline execution."""
        pipeline_name = execution["pipelineName"]
        execution_id = execution["pipelineExecutionId"]
        
        try:
            response = await self.client.list_stage_executions(
                pipelineName=pipeline_name,
                pipelineExecutionId=execution_id
            )
            stage_executions = response.get("stageExecutionDetails", [])
            
            logger.info(f"Found {len(stage_executions)} stage executions for pipeline {pipeline_name} execution {execution_id}")
            
            results: List[Dict[str, Any]] = []
            for stage_execution in stage_executions:
                results.append({
                    "pipelineName": pipeline_name,
                    "pipelineExecutionId": execution_id,
                    "pipelineVersion": stage_execution.get("pipelineVersion"),
                    "stageName": stage_execution.get("stageName", ""),
                    "status": stage_execution.get("stageExecutionStatus"),
                })
            
            return results
        except self.client.exceptions.ClientError as e:
            if e.response.get("Error", {}).get("Code") in ["PipelineNotFoundException", "PipelineExecutionNotFoundException"]:
                logger.info(f"Pipeline {pipeline_name} or execution {execution_id} not found")
                return []
            else:
                logger.error(f"Error fetching stage executions for pipeline {pipeline_name} execution {execution_id}: {e}")
                raise


class GetActionExecutionsAction(Action):
    """Fetches action execution details within stage executions."""

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
                stage_name = resources[idx].get("stageName", "unknown")
                logger.error(f"Error fetching action executions for stage '{stage_name}': {action_execution_result}")
                continue
            
            # Merge action executions into the stage execution
            stage_execution = resources[idx].copy()
            stage_execution["actionExecutionDetails"] = cast(List[Dict[str, Any]], action_execution_result)
            results.append(stage_execution)
        
        return results

    async def _fetch_action_executions(self, stage_execution: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch action executions for a specific stage execution."""
        pipeline_name = stage_execution["pipelineName"]
        execution_id = stage_execution["pipelineExecutionId"]
        stage_name = stage_execution["stageName"]
        
        try:
            response = await self.client.list_action_executions(
                pipelineName=pipeline_name,
                filter={
                    'pipelineExecutionId': execution_id
                }
            )
            action_executions = response.get("actionExecutionDetails", [])
            
            # Filter action executions for this specific stage
            stage_actions = [
                action for action in action_executions
                if action.get("stageName") == stage_name
            ]
            
            logger.info(f"Found {len(stage_actions)} action executions for stage {stage_name} in pipeline {pipeline_name}")
            
            results: List[Dict[str, Any]] = []
            for action in stage_actions:
                results.append({
                    "actionExecutionId": action.get("actionExecutionId", ""),
                    "actionName": action.get("actionName", ""),
                    "pipelineName": pipeline_name,
                    "pipelineVersion": action.get("pipelineVersion"),
                    "stageName": stage_name,
                    "status": action.get("status"),
                    "token": action.get("token"),
                    "lastStatusChange": action.get("lastStatusChange"),
                    "externalExecutionId": action.get("externalExecutionId"),
                    "externalExecutionUrl": action.get("externalExecutionUrl"),
                    "percentComplete": action.get("percentComplete"),
                    "errorDetails": action.get("errorDetails"),
                })
            
            return results
        except self.client.exceptions.ClientError as e:
            if e.response.get("Error", {}).get("Code") in ["PipelineNotFoundException", "PipelineExecutionNotFoundException"]:
                logger.info(f"Pipeline {pipeline_name} or execution {execution_id} not found")
                return []
            else:
                logger.error(f"Error fetching action executions for stage {stage_name}: {e}")
                raise


class CodePipelineStageExecutionActionsMap(ActionMap):
    """Groups all actions for CodePipeline stage execution resource type."""
    defaults: List[Type[Action]] = [
        ListPipelinesAction,
        GetPipelineExecutionsAction,
        GetStageExecutionsAction,
        GetActionExecutionsAction,
    ]
    options: List[Type[Action]] = []