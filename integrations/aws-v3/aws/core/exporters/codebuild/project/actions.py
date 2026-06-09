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
        response = await self.client.batch_get_projects(names=resources)
        projects = response.get("projects", [])
        logger.info(
            f"Successfully fetched details for {len(projects)} CodeBuild projects"
        )

        return [
            {
                "Arn": project.get("arn", ""),
                "Artifacts": project.get("artifacts"),
                "AutoRetryLimit": project.get("autoRetryLimit"),
                "Badge": project.get("badge"),
                "BuildBatchConfig": project.get("buildBatchConfig"),
                "Cache": project.get("cache"),
                "ConcurrentBuildLimit": project.get("concurrentBuildLimit"),
                "Created": project.get("created"),
                "Description": project.get("description"),
                "EncryptionKey": project.get("encryptionKey"),
                "Environment": project.get("environment"),
                "FileSystemLocations": project.get("fileSystemLocations", []),
                "LastModified": project.get("lastModified"),
                "LogsConfig": project.get("logsConfig"),
                "Name": project.get("name", ""),
                "ProjectVisibility": project.get("projectVisibility"),
                "PublicProjectAlias": project.get("publicProjectAlias"),
                "QueuedTimeoutInMinutes": project.get("queuedTimeoutInMinutes"),
                "ResourceAccessRole": project.get("resourceAccessRole"),
                "SecondaryArtifacts": project.get("secondaryArtifacts", []),
                "SecondarySources": project.get("secondarySources", []),
                "SecondarySourceVersions": project.get("secondarySourceVersions", []),
                "ServiceRole": project.get("serviceRole"),
                "Source": project.get("source"),
                "SourceVersion": project.get("sourceVersion"),
                "Tags": project.get("tags", []),
                "TimeoutInMinutes": project.get("timeoutInMinutes"),
                "VpcConfig": project.get("vpcConfig"),
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
