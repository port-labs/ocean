from typing import Dict, Any, List, Type, cast

from aws.core.exporters.codepipeline.utils.base_pipeline_action import PipelineAction
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger
import asyncio


class ListPipelinesAction(Action):
    """Processes the initial list of pipelines from AWS."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return resources


class GetPipelineDetailsAction(PipelineAction):
    """Fetches detailed information about CodePipeline pipelines."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not resources:
            return []

        details = await asyncio.gather(
            *(self._fetch_pipeline_details(resource) for resource in resources),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, detail_result in enumerate(details):
            if isinstance(detail_result, Exception):
                pipeline_name = resources[idx].get("name", "unknown")
                logger.error(
                    f"Error fetching details for pipeline '{pipeline_name}': {detail_result}"
                )
                results.append({})
            else:
                results.append(detail_result)
        return results

    async def _fetch_pipeline_details(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        pipeline_name = resource["name"]
        response = await self._get_pipeline(pipeline_name)
        logger.info(f"Successfully fetched details for pipeline {pipeline_name}")

        return {
            **response.get("metadata", {}),
            **response.get("pipeline", {}),
        }


class GetPipelineTagsAction(PipelineAction):
    """Fetches tags for CodePipeline pipelines."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not resources:
            return []

        tags = await asyncio.gather(
            *(self._fetch_pipeline_tags(resource) for resource in resources),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, tag_result in enumerate(tags):
            if isinstance(tag_result, Exception):
                pipeline_name = resources[idx].get("name", "unknown")
                logger.error(
                    f"Error fetching tags for pipeline '{pipeline_name}': {tag_result}"
                )
                results.append({})
                continue
            results.append(cast(Dict[str, Any], tag_result))
        return results

    async def _fetch_pipeline_tags(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        pipeline_name = resource["name"]

        pipeline_response = await self._get_pipeline(pipeline_name)
        pipeline_arn = pipeline_response.get("metadata", {}).get("pipelineArn")

        response = await self.client.list_tags_for_resource(resourceArn=pipeline_arn)
        tags_list = response.get("tags", [])

        tags_dict = {tag.get("key", ""): tag.get("value", "") for tag in tags_list}

        logger.info(f"Successfully fetched tags for pipeline {pipeline_name}")
        return {"tags": tags_dict}


class PipelineActionsMap(ActionMap):
    """Groups all actions for CodePipeline pipeline resource type."""

    defaults: List[Type[Action]] = [
        GetPipelineDetailsAction,
        GetPipelineTagsAction,
        ListPipelinesAction,
    ]
    options: List[Type[Action]] = []
