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


class CodeBuildProjectActionsMap(ActionMap):
    """Groups all actions for CodeBuild project resource type."""

    defaults: List[Type[Action]] = [
        ListProjectsAction,
        GetProjectDetailsAction,
    ]
    options: List[Type[Action]] = []
