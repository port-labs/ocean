from typing import Dict, Any, List, Type
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger


class GetBuildDetailsAction(Action):
    """Fetches detailed information about CodeBuild project build runs."""

    async def _execute(self, resources: list[str]) -> List[Dict[str, Any]]:
        if not resources:
            return []

        try:
            response = await self.client.batch_get_builds(ids=resources)
        except Exception as e:
            logger.error(f"Error fetching build details: {e}")
            raise

        builds = response.get("builds", [])
        logger.info(f"Successfully fetched details for {len(builds)} build runs")
        return [
            {
                "Arn": build.get("arn", ""),
                "Artifacts": build.get("artifacts", []),
                "AutoRetryConfig": build.get("autoRetryConfig"),
                "BuildBatchArn": build.get("buildBatchArn"),
                "BuildComplete": build.get("buildComplete"),
                "BuildNumber": build.get("buildNumber"),
                "BuildStatus": build.get("buildStatus"),
                "Cache": build.get("cache"),
                "CurrentPhase": build.get("currentPhase"),
                "DebugSession": build.get("debugSession"),
                "EncryptionKey": build.get("encryptionKey"),
                "EndTime": build.get("endTime"),
                "Environment": build.get("environment"),
                "ExportedEnvironmentVariables": build.get(
                    "exportedEnvironmentVariables", []
                ),
                "FileSystemLocations": build.get("fileSystemLocations", []),
                "Id": build.get("id", ""),
                "Initiator": build.get("initiator"),
                "Logs": build.get("logs"),
                "NetworkInterface": build.get("networkInterface"),
                "Phases": build.get("phases", []),
                "ProjectName": build.get("projectName", ""),
                "QueuedTimeoutInMinutes": build.get("queuedTimeoutInMinutes"),
                "ReportArns": build.get("reportArns", []),
                "ResolvedSourceVersion": build.get("resolvedSourceVersion"),
                "SecondaryArtifacts": build.get("secondaryArtifacts", []),
                "SecondarySources": build.get("secondarySources", []),
                "SecondarySourceVersions": build.get("secondarySourceVersions", []),
                "ServiceRole": build.get("serviceRole"),
                "Source": build.get("source"),
                "SourceVersion": build.get("sourceVersion"),
                "StartTime": build.get("startTime"),
                "TimeoutInMinutes": build.get("timeoutInMinutes"),
                "VpcConfig": build.get("vpcConfig"),
            }
            for build in builds
        ]



class ListBuildsAction(Action):
    """Processes the initial list of build runs from AWS."""

    async def _execute(self, resources: list[str]) -> List[Dict[str, Any]]:
        return [{"Id": build_id} for build_id in resources]


class BuildRunActionsMap(ActionMap):
    """Groups all actions for CodeBuild project build runs."""

    defaults: List[Type[Action]] = [
        GetBuildDetailsAction,
        ListBuildsAction,
    ]
    options: List[Type[Action]] = []
