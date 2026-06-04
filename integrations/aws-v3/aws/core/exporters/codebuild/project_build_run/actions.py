from typing import Dict, Any, List, Type
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger


class GetBuildDetailsAction(Action):
    """Fetches detailed information about CodeBuild project build runs."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not resources:
            return []

        build_ids = [resource.get("id") for resource in resources]

        try:
            response = await self.client.batch_get_builds(ids=build_ids)
            builds = response.get("builds", [])

            logger.info(f"Successfully fetched details for {len(builds)} build runs")

            return [
                {
                    "Id": build.get("id", ""),
                    "ProjectName": build.get("projectName", ""),
                    "Arn": build.get("arn", ""),
                    "BuildNumber": build.get("buildNumber"),
                    "StartTime": build.get("startTime"),
                    "EndTime": build.get("endTime"),
                    "CurrentPhase": build.get("currentPhase"),
                    "BuildStatus": build.get("buildStatus"),
                    "SourceVersion": build.get("sourceVersion"),
                    "ResolvedSourceVersion": build.get("resolvedSourceVersion"),
                    "ProjectVersion": build.get("projectVersion"),
                    "Artifacts": build.get("artifacts", []),
                    "Cache": build.get("cache"),
                    "Environment": build.get("environment"),
                    "ServiceRole": build.get("serviceRole"),
                    "Logs": build.get("logs"),
                    "TimeoutInMinutes": build.get("timeoutInMinutes"),
                    "QueuedTimeoutInMinutes": build.get("queuedTimeoutInMinutes"),
                    "BuildComplete": build.get("buildComplete"),
                    "Initiator": build.get("initiator"),
                    "VpcConfig": build.get("vpcConfig"),
                    "NetworkInterface": build.get("networkInterface"),
                    "EncryptionKey": build.get("encryptionKey"),
                    "ExportedEnvironmentVariables": build.get(
                        "exportedEnvironmentVariables", []
                    ),
                    "ReportArns": build.get("reportArns", []),
                    "FileSystemLocations": build.get("fileSystemLocations", []),
                    "DebugSession": build.get("debugSession"),
                    "BuildBatchArn": build.get("buildBatchArn"),
                }
                for build in builds
            ]
        except Exception as e:
            logger.error(f"Error fetching build details: {e}")
            raise


class ListBuildsAction(Action):
    """Processes the initial list of build runs from AWS."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for resource in resources:
            build_id = resource.get("id")
            if build_id:
                data = {
                    "id": build_id,
                    "Id": build_id,
                }
                results.append(data)
        return results


class BuildRunActionsMap(ActionMap):
    """Groups all actions for CodeBuild project build runs."""

    defaults: List[Type[Action]] = [
        GetBuildDetailsAction,
        ListBuildsAction,
    ]
    options: List[Type[Action]] = []
