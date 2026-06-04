from typing import Dict, Any, List, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger
import asyncio


class ListProjectsAction(Action):
    """Processes the initial list of projects from AWS."""

    async def _execute(self, resources: List[str]) -> List[Dict[str, Any]]:
        return [{"name": project, "id": project} for project in resources]


class GetProjectDetailsAction(Action):
    """Fetches detailed information about CodeBuild projects."""

    async def _execute(self, resources: List[str]) -> List[Dict[str, Any]]:
        if not resources:
            return []

        response = await self.client.batch_get_projects(names=resources)
        projects = response.get("projects", [])
        logger.info(
            f"Successfully fetched details for {len(projects)} CodeBuild projects"
        )

        return [
            {
                "name": project.get("name", ""),
                "arn": project.get("arn", ""),
                "description": project.get("description"),
                "source": project.get("source"),
                "secondarySources": project.get("secondarySources", []),
                "sourceVersion": project.get("sourceVersion"),
                "secondarySourceVersions": project.get("secondarySourceVersions", []),
                "artifacts": project.get("artifacts"),
                "secondaryArtifacts": project.get("secondaryArtifacts", []),
                "cache": project.get("cache"),
                "environment": project.get("environment"),
                "serviceRole": project.get("serviceRole"),
                "timeoutInMinutes": project.get("timeoutInMinutes"),
                "queuedTimeoutInMinutes": project.get("queuedTimeoutInMinutes"),
                "encryptionKey": project.get("encryptionKey"),
                "tags": project.get("tags", []),
                "vpcConfig": project.get("vpcConfig"),
                "badge": project.get("badge"),
                "logsConfig": project.get("logsConfig"),
                "fileSystemLocations": project.get("fileSystemLocations", []),
                "buildBatchConfig": project.get("buildBatchConfig"),
                "concurrentBuildLimit": project.get("concurrentBuildLimit"),
                "projectVisibility": project.get("projectVisibility"),
                "publicReadOnlyAccess": project.get("publicReadOnlyAccess"),
                "resourceAccessRole": project.get("resourceAccessRole"),
                "created": project.get("created"),
                "lastModified": project.get("lastModified"),
                "webhook": project.get("webhook"),
            }
            for project in projects
        ]


class GetProjectWebhooksAction(Action):
    """Fetches webhook information for CodeBuild projects."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not resources:
            return []

        results = await asyncio.gather(
            *(self._fetch_project_webhooks(resource) for resource in resources),
            return_exceptions=True,
        )

        processed_results: List[Dict[str, Any]] = []
        for idx, webhook_result in enumerate(results):
            if isinstance(webhook_result, Exception):
                project_name = resources[idx].get("name", "unknown")
                logger.error(
                    f"Error fetching webhooks for project '{project_name}': {webhook_result}"
                )
                continue
            processed_results.append(cast(Dict[str, Any], webhook_result))
        return processed_results

    async def _fetch_project_webhooks(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = await self.client.list_webhooks_for_project(
                projectName=resource["name"]
            )
            return {"webhook": response.get("webhooks", [])}
        except self.client.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "ResourceNotFoundException":
                return {"webhook": []}
            else:
                logger.error(
                    f"Unexpected error fetching webhooks for {resource['name']}: {e}"
                )
                raise


class CodeBuildProjectActionsMap(ActionMap):
    """Groups all actions for CodeBuild project resource type."""

    defaults: List[Type[Action]] = [
        ListProjectsAction,
        GetProjectDetailsAction,
    ]
    options: List[Type[Action]] = [
        GetProjectWebhooksAction,
    ]
