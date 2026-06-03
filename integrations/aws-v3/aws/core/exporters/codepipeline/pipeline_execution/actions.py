from typing import Any, Type, cast, Dict, List
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import is_recoverable_aws_exception
from loguru import logger
import asyncio


class GetPipelineExecutionDetailsAction(Action):
    """Fetches detailed information about pipeline executions."""

    async def _execute(self, executions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not executions:
            return []

        details = await asyncio.gather(
            *(self._fetch_pipeline_execution_details(execution) for execution in executions),
            return_exceptions=True,
        )

        results: list[dict[str, Any]] = []
        for idx, detail_result in enumerate(details):
            if isinstance(detail_result, Exception):
                execution_id = executions[idx].get("pipelineExecutionId", "unknown")
                pipeline_name = executions[idx].get("pipelineName", "unknown")
                if is_recoverable_aws_exception(detail_result):
                    logger.warning(
                        f"Skipping pipeline execution details for pipeline '{pipeline_name}' execution '{execution_id}': {detail_result}"
                    )
                    continue
                else:
                    logger.error(
                        f"Error fetching details for pipeline '{pipeline_name}' execution '{execution_id}': {detail_result}"
                    )
                    raise detail_result
            results.append(cast(dict[str, Any], detail_result))
        
        logger.info(f"Successfully fetched details for {len(results)} pipeline executions")
        return results

    async def _fetch_pipeline_execution_details(self, execution: dict[str, Any]) -> dict[str, Any]:
        pipeline_name = execution["pipelineName"]
        execution_id = execution["pipelineExecutionId"]
        
        response = await self.client.get_pipeline_execution(
            pipelineName=pipeline_name,
            pipelineExecutionId=execution_id
        )
        
        execution_detail = response["pipelineExecution"]
        
        logger.info(f"Successfully fetched details for pipeline '{pipeline_name}' execution '{execution_id}'")
        
        return {
            "pipelineArn": execution_detail.get("pipelineArn", ""),
            "pipelineName": execution_detail.get("pipelineName", ""),
            "pipelineVersion": execution_detail.get("pipelineVersion"),
            "pipelineExecutionId": execution_detail.get("pipelineExecutionId", ""),
            "status": execution_detail.get("status"),
            "statusSummary": execution_detail.get("statusSummary"),
            "artifactRevisions": execution_detail.get("artifactRevisions", []),
            "variableValues": execution_detail.get("variableValues"),
            "trigger": execution_detail.get("trigger"),
            "executionMode": execution_detail.get("executionMode"),
            "rollbackMetadata": execution_detail.get("rollbackMetadata"),
            "pipelineExecutionDisplayName": execution_detail.get("pipelineExecutionDisplayName"),
            "createdAt": execution_detail.get("createdAt").isoformat() if execution_detail.get("createdAt") else None,
            "updatedAt": execution_detail.get("updatedAt").isoformat() if execution_detail.get("updatedAt") else None,
        }


class GetPipelineExecutionStagesAction(Action):
    """Fetches stage execution details for pipeline executions."""

    async def _execute(self, executions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not executions:
            return []

        stages = await asyncio.gather(
            *(self._fetch_pipeline_execution_stages(execution) for execution in executions),
            return_exceptions=True,
        )

        results: list[dict[str, Any]] = []
        for idx, stage_result in enumerate(stages):
            if isinstance(stage_result, Exception):
                execution_id = executions[idx].get("pipelineExecutionId", "unknown")
                pipeline_name = executions[idx].get("pipelineName", "unknown")
                if is_recoverable_aws_exception(stage_result):
                    logger.warning(
                        f"Skipping stage details for pipeline '{pipeline_name}' execution '{execution_id}': {stage_result}"
                    )
                    continue
                else:
                    logger.error(
                        f"Error fetching stage details for pipeline '{pipeline_name}' execution '{execution_id}': {stage_result}"
                    )
                    raise stage_result
            results.append(cast(dict[str, Any], stage_result))
        
        logger.info(f"Successfully fetched stage details for {len(results)} pipeline executions")
        return results

    async def _fetch_pipeline_execution_stages(self, execution: dict[str, Any]) -> dict[str, Any]:
        pipeline_name = execution["pipelineName"]
        execution_id = execution["pipelineExecutionId"]
        
        response = await self.client.list_stage_executions(
            pipelineName=pipeline_name,
            pipelineExecutionId=execution_id
        )
        
        stages = response.get("stageExecutions", [])
        
        logger.info(f"Successfully fetched stage details for pipeline '{pipeline_name}' execution '{execution_id}'")
        
        return {"stageStates": stages}


class GetPipelineTagsAction(Action):
    """Fetches tags for pipelines."""

    async def _execute(self, executions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not executions:
            return []

        tags = await asyncio.gather(
            *(self._fetch_pipeline_tags(execution) for execution in executions),
            return_exceptions=True,
        )

        results: list[dict[str, Any]] = []
        for idx, tag_result in enumerate(tags):
            if isinstance(tag_result, Exception):
                pipeline_arn = executions[idx].get("pipelineArn", "unknown")
                if is_recoverable_aws_exception(tag_result):
                    logger.warning(
                        f"Skipping tags for pipeline '{pipeline_arn}': {tag_result}"
                    )
                    results.append({"tags": []})
                    continue
                else:
                    logger.error(f"Error fetching tags for pipeline '{pipeline_arn}': {tag_result}")
                    raise tag_result
            results.append(cast(dict[str, Any], tag_result))
        
        logger.info(f"Successfully fetched tags for {len(results)} pipelines")
        return results

    async def _fetch_pipeline_tags(self, execution: dict[str, Any]) -> dict[str, Any]:
        pipeline_arn = execution.get("pipelineArn")
        if not pipeline_arn:
            return {"tags": []}
        
        try:
            response = await self.client.list_tags_for_resource(
                resourceArn=pipeline_arn
            )
            tags = response.get("tags", [])
            return {"tags": tags}
        except Exception as e:
            # If tags are not available, return empty list
            logger.debug(f"Could not fetch tags for pipeline '{pipeline_arn}': {e}")
            return {"tags": []}


class ListPipelineExecutionsAction(Action):
    """Processes the initial list of pipeline executions."""

    async def _execute(self, executions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for execution in executions:
            data = {
                "pipelineName": execution.get("pipelineName", ""),
                "pipelineExecutionId": execution.get("pipelineExecutionId", ""),
                "status": execution.get("status"),
                "trigger": execution.get("trigger"),
                "createdAt": execution.get("createdAt").isoformat() if execution.get("createdAt") else None,
                "updatedAt": execution.get("updatedAt").isoformat() if execution.get("updatedAt") else None,
            }
            results.append(data)
        return results


class CodePipelinePipelineExecutionActionsMap(ActionMap):
    """Groups all actions for CodePipeline pipeline executions."""
    
    defaults: list[Type[Action]] = [
        ListPipelineExecutionsAction,
        GetPipelineExecutionDetailsAction,
        GetPipelineExecutionStagesAction,
    ]
    options: list[Type[Action]] = [
        GetPipelineTagsAction,
    ]