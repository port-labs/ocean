from typing import Dict, Any, List, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger
import asyncio


class ListPipelinesAction(Action):
    """Lists all CodePipeline pipelines to find stages."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute the action to list all pipelines and extract stages."""
        try:
            # Get all pipelines
            response = await self.client.list_pipelines()
            pipelines = response.get("pipelines", [])

            if not pipelines:
                logger.info("No pipelines found in this region")
                return []

            # Fetch detailed pipeline information for each pipeline to extract stages
            pipeline_details = await asyncio.gather(
                *(self._fetch_pipeline_details(pipeline) for pipeline in pipelines),
                return_exceptions=True,
            )

            results: List[Dict[str, Any]] = []
            for idx, detail_result in enumerate(pipeline_details):
                if isinstance(detail_result, Exception):
                    pipeline_name = pipelines[idx].get("name", "unknown")
                    logger.error(f"Error fetching pipeline details for '{pipeline_name}': {detail_result}")
                    continue

                pipeline_data = cast(Dict[str, Any], detail_result)
                # Extract stages from the pipeline
                stages = pipeline_data.get("pipeline", {}).get("stages", [])
                for stage in stages:
                    stage_data = {
                        "Name": stage.get("name", ""),
                        "PipelineName": pipeline_data.get("pipeline", {}).get("name", ""),
                        "PipelineArn": pipeline_data.get("pipeline", {}).get("arn", ""),
                        "Actions": stage.get("actions", []),
                        "Blockers": stage.get("blockers", []),
                        "pipeline_name": pipeline_data.get("pipeline", {}).get("name", ""),
                        "stage_name": stage.get("name", "")
                    }
                    results.append(stage_data)

            logger.info(f"Found {len(results)} stages across {len(pipelines)} pipelines")
            return results

        except Exception as e:
            logger.error(f"Error listing pipelines: {e}")
            return []

    async def _fetch_pipeline_details(self, pipeline: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch detailed information about a specific pipeline."""
        pipeline_name = pipeline["name"]
        response = await self.client.get_pipeline(name=pipeline_name)
        return response


class GetStageDetailsAction(Action):
    """Fetches detailed information about specific pipeline stages."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not resources:
            return []

        # Get pipeline state to get additional stage information
        stage_states = await asyncio.gather(
            *(self._fetch_stage_state(resource) for resource in resources),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, state_result in enumerate(stage_states):
            resource = resources[idx]
            if isinstance(state_result, Exception):
                pipeline_name = resource.get("PipelineName", "unknown")
                stage_name = resource.get("Name", "unknown")
                logger.error(f"Error fetching stage state for pipeline '{pipeline_name}', stage '{stage_name}': {state_result}")
                # Still include the basic data even if we can't get state
                results.append(resource)
                continue

            state_data = cast(Dict[str, Any], state_result)
            # Merge state information with existing resource data
            enhanced_resource = {**resource}

            # Add stage state information if available
            stage_states_list = state_data.get("stageStates", [])
            for stage_state in stage_states_list:
                if stage_state.get("stageName") == resource.get("Name"):
                    enhanced_resource.update({
                        "StageExecution": stage_state.get("latestExecution", {}),
                        "InboundTransitionState": stage_state.get("inboundTransitionState", {}),
                    })
                    break

            results.append(enhanced_resource)

        return results

    async def _fetch_stage_state(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch the state information for a stage."""
        pipeline_name = resource.get("name")
        if not pipeline_name:
            raise ValueError("Pipeline name is required to fetch stage state")

        response = await self.client.get_pipeline_state(name=pipeline_name)
        return response


class CodePipelineStageActionsMap(ActionMap):
    """Groups all actions for CodePipeline stages."""
    defaults: List[Type[Action]] = [
        ListPipelinesAction,
        GetStageDetailsAction,
    ]
    options: List[Type[Action]] = []
