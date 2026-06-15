from dataclasses import dataclass
from typing import Dict, Any, List, Type, cast

from aws.core.exporters.codepipeline.utils.base_pipeline_action import PipelineAction
from aws.core.interfaces.action import Action, ActionMap, BaseActionInput
from loguru import logger
import asyncio


@dataclass
class CodePipelinePipelineActionInput(BaseActionInput[dict[str, Any]]):
    region: str
    account_id: str


class ListPipelinesAction(Action[CodePipelinePipelineActionInput]):
    """Processes the initial list of pipelines from AWS."""

    async def _execute(
        self, resources: CodePipelinePipelineActionInput
    ) -> list[dict[str, Any]]:
        return resources.items


class GetPipelineDetailsAction(PipelineAction[CodePipelinePipelineActionInput]):
    """Fetches detailed information about CodePipeline pipelines."""

    async def _execute(
        self, resources: CodePipelinePipelineActionInput
    ) -> list[dict[str, Any]]:
        if not resources:
            return []

        details = await asyncio.gather(
            *(
                self._fetch_pipeline_details(
                    resource, region=resources.region, account_id=resources.account_id
                )
                for resource in resources.items
            ),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, detail_result in enumerate(details):
            if isinstance(detail_result, dict):
                results.append(detail_result)
            else:
                pipeline_name = resources.items[idx].get("name", "unknown")
                logger.error(
                    f"Error fetching details for pipeline '{pipeline_name}': {detail_result}"
                )
                results.append({})
        return results

    async def _fetch_pipeline_details(
        self, resource: Dict[str, Any], region: str, account_id: str
    ) -> dict[str, Any]:
        pipeline_name = resource["name"]
        response = await self._get_pipeline(
            pipeline_name, cache_keys={"region": region, "account_id": account_id}
        )
        logger.info(f"Successfully fetched details for pipeline {pipeline_name}")

        return {
            **response.get("metadata", {}),
            **response.get("pipeline", {}),
        }


class GetPipelineTagsAction(PipelineAction[CodePipelinePipelineActionInput]):
    """Fetches tags for CodePipeline pipelines."""

    async def _execute(
        self, resources: CodePipelinePipelineActionInput
    ) -> list[Dict[str, Any]]:
        if not resources:
            return []

        tags = await asyncio.gather(
            *(
                self._fetch_pipeline_tags(
                    resource, region=resources.region, account_id=resources.account_id
                )
                for resource in resources.items
            ),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, tag_result in enumerate(tags):
            if isinstance(tag_result, Exception):
                pipeline_name = resources.items[idx].get("name", "unknown")
                logger.error(
                    f"Error fetching tags for pipeline '{pipeline_name}': {tag_result}"
                )
                results.append({})
                continue
            results.append(cast(Dict[str, Any], tag_result))
        return results

    async def _fetch_pipeline_tags(
        self, resource: dict[str, Any], region: str, account_id: str
    ) -> dict[str, Any]:
        pipeline_response = await self._get_pipeline(
            resource["name"], cache_keys={"region": region, "account_id": account_id}
        )
        pipeline_arn = pipeline_response.get("metadata", {}).get("pipelineArn")

        response = await self.client.list_tags_for_resource(resourceArn=pipeline_arn)
        logger.info(f"Successfully fetched tags for pipeline {resource["name"]}")
        return response


class PipelineActionsMap(ActionMap[CodePipelinePipelineActionInput]):
    """Groups all actions for CodePipeline pipeline resource type."""

    defaults: List[Type[Action[CodePipelinePipelineActionInput]]] = [
        GetPipelineDetailsAction,
        GetPipelineTagsAction,
        ListPipelinesAction,
    ]
    options: List[Type[Action[CodePipelinePipelineActionInput]]] = []
