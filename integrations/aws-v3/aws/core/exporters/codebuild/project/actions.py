from typing import Dict, Any, List, Type
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger


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
        logger.info(f"Successfully fetched details for {len(projects)} CodeBuild projects")

        return [
            {
                "Name": project.get("name", ""),
                "Arn": project.get("arn", ""),
                "AutoRetryLimit": project.get("autoRetryLimit"),
                "Description": project.get("description"),
                "Source": project.get("source"),
                "SecondarySources": project.get("secondarySources", []),
                "SourceVersion": project.get("sourceVersion"),
                "SecondarySourceVersions": project.get("secondarySourceVersions", []),
                "Artifacts": project.get("artifacts"),
                "SecondaryArtifacts": project.get("secondaryArtifacts", []),
                "Cache": project.get("cache"),
                "Environment": project.get("environment"),
                "ServiceRole": project.get("serviceRole"),
                "TimeoutInMinutes": project.get("timeoutInMinutes"),
                "QueuedTimeoutInMinutes": project.get("queuedTimeoutInMinutes"),
                "EncryptionKey": project.get("encryptionKey"),
                "Tags": project.get("tags", []),
                "VpcConfig": project.get("vpcConfig"),
                "Badge": project.get("badge"),
                "LogsConfig": project.get("logsConfig"),
                "FileSystemLocations": project.get("fileSystemLocations", []),
                "BuildBatchConfig": project.get("buildBatchConfig"),
                "ConcurrentBuildLimit": project.get("concurrentBuildLimit"),
                "ProjectVisibility": project.get("projectVisibility"),
                "PublicProjectAlias": project.get("publicProjectAlias"),
                "ResourceAccessRole": project.get("resourceAccessRole"),
                "Created": project.get("created"),
                "LastModified": project.get("lastModified"),
                "Webhook": project.get("webhook"),
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
