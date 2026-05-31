from typing import Dict, Any, List, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger
import asyncio


class GetPipelineDetailsAction(Action):
    """Fetches detailed information about CodePipeline pipelines."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not resources:
            return []

        # Use asyncio.gather for concurrent API calls
        details = await asyncio.gather(
            *(self._fetch_pipeline_details(resource) for resource in resources),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, detail_result in enumerate(details):
            if isinstance(detail_result, Exception):
                pipeline_name = resources[idx].get("name", "unknown")
                logger.error(f"Error fetching details for pipeline '{pipeline_name}': {detail_result}")
                continue
            results.append(cast(Dict[str, Any], detail_result))
        return results

    async def _fetch_pipeline_details(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        pipeline_name = resource["name"]
        
        try:
            # Get pipeline details
            response = await self.client.get_pipeline(name=pipeline_name)
            pipeline = response.get("pipeline", {})
            metadata = response.get("metadata", {})

            logger.info(f"Successfully fetched details for pipeline {pipeline_name}")

            # Transform AWS response to our model format
            artifact_store = pipeline.get("artifactStore", {})
            artifact_stores = pipeline.get("artifactStores", {})
            
            return {
                "Name": pipeline.get("name", pipeline_name),
                "Arn": metadata.get("pipelineArn", ""),
                "RoleArn": pipeline.get("roleArn", ""),
                "ArtifactStore": {
                    "location": artifact_store.get("location"),
                    "type": artifact_store.get("type"),
                    "encryptionKey": artifact_store.get("encryptionKey"),
                } if artifact_store else None,
                "ArtifactStores": {
                    region: {
                        "location": store.get("location"),
                        "type": store.get("type"),
                        "encryptionKey": store.get("encryptionKey"),
                    }
                    for region, store in artifact_stores.items()
                },
                "Stages": [
                    {
                        "name": stage.get("name"),
                        "actions": stage.get("actions", []),
                        "blockers": stage.get("blockers", []),
                    }
                    for stage in pipeline.get("stages", [])
                ],
                "Version": pipeline.get("version"),
                "ExecutionMode": pipeline.get("executionMode"),
                "PipelineType": pipeline.get("pipelineType"),
                "Variables": pipeline.get("variables", []),
                "Triggers": pipeline.get("triggers", []),
                "Created": metadata.get("created").isoformat() if metadata.get("created") else None,
                "Updated": metadata.get("updated").isoformat() if metadata.get("updated") else None,
            }
        except self.client.exceptions.PipelineNotFoundException:
            logger.warning(f"Pipeline {pipeline_name} not found")
            return {}
        except Exception as e:
            logger.error(f"Error fetching pipeline details for {pipeline_name}: {e}")
            raise


class GetPipelineTagsAction(Action):
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
                logger.error(f"Error fetching tags for pipeline '{pipeline_name}': {tag_result}")
                continue
            results.append(cast(Dict[str, Any], tag_result))
        return results

    async def _fetch_pipeline_tags(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        pipeline_name = resource["name"]
        
        try:
            # Get pipeline ARN first to fetch tags
            pipeline_response = await self.client.get_pipeline(name=pipeline_name)
            pipeline_arn = pipeline_response.get("metadata", {}).get("pipelineArn")
            
            if not pipeline_arn:
                logger.warning(f"No ARN found for pipeline {pipeline_name}")
                return {"Tags": {}}

            response = await self.client.list_tags_for_resource(resourceArn=pipeline_arn)
            tags_list = response.get("tags", [])
            
            # Convert tags list to dictionary
            tags_dict = {tag.get("key", ""): tag.get("value", "") for tag in tags_list}
            
            logger.info(f"Successfully fetched tags for pipeline {pipeline_name}")
            return {"Tags": tags_dict}
            
        except self.client.exceptions.PipelineNotFoundException:
            logger.warning(f"Pipeline {pipeline_name} not found when fetching tags")
            return {"Tags": {}}
        except self.client.exceptions.ResourceNotFoundException:
            logger.warning(f"No tags found for pipeline {pipeline_name}")
            return {"Tags": {}}
        except Exception as e:
            logger.error(f"Error fetching tags for pipeline {pipeline_name}: {e}")
            return {"Tags": {}}


class ListPipelinesAction(Action):
    """Processes the initial list of pipelines from AWS."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for resource in resources:
            data = {
                "name": resource.get("name", ""),
                "version": resource.get("version"),
                "created": resource.get("created").isoformat() if resource.get("created") else None,
                "updated": resource.get("updated").isoformat() if resource.get("updated") else None,
            }
            results.append(data)
        return results


class PipelineActionsMap(ActionMap):
    """Groups all actions for CodePipeline pipeline resource type."""
    
    defaults: List[Type[Action]] = [
        GetPipelineDetailsAction,
        GetPipelineTagsAction,
        ListPipelinesAction,
    ]
    options: List[Type[Action]] = []