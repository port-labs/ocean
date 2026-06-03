from typing import Dict, Any, List, Type, cast
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
                    "ExportedEnvironmentVariables": build.get("exportedEnvironmentVariables", []),
                    "ReportArns": build.get("reportArns", []),
                    "FileSystemLocations": build.get("fileSystemLocations", []),
                    "DebugSession": build.get("debugSession"),
                    "BuildBatchArn": build.get("buildBatchArn"),
                } for build in builds
            ]
        except Exception as e:
            logger.error(f"Error fetching build details: {e}")
            raise


class ListBuildsAction(Action):
    """Processes the initial list of build runs from AWS."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for resource in resources:
            # Extract build ID from the resource
            build_id = resource.get("id", resource.get("Id", ""))
            if build_id:
                data = {
                    "id": build_id,
                    "Id": build_id,
                    # Add any basic fields available from list operation
                }
                results.append(data)
        return results


class GetProjectBuildsAction(Action):
    """Fetches build runs for specific projects if needed."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not resources:
            return []

        # This action can be used to get builds for specific projects
        # if we need to filter by project name
        results: List[Dict[str, Any]] = []

        # Group resources by project if needed
        project_builds = {}
        for resource in resources:
            project_name = resource.get("projectName")
            if project_name:
                if project_name not in project_builds:
                    project_builds[project_name] = []
                project_builds[project_name].append(resource)

        # For each project, we can get additional build information if needed
        for project_name, builds in project_builds.items():
            logger.info(f"Processing {len(builds)} builds for project {project_name}")
            results.extend(builds)

        return results


class ProjectBuildRunActionsMap(ActionMap):
    """Groups all actions for CodeBuild project build runs."""
    defaults: List[Type[Action]] = [
        GetBuildDetailsAction,
        ListBuildsAction,
    ]
    options: List[Type[Action]] = [
        GetProjectBuildsAction,
    ]
