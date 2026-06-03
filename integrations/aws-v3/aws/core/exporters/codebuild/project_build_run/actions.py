from typing import Dict, Any, List, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger
import asyncio


class GetBuildDetailsAction(Action):
    """Fetches detailed information about CodeBuild project build runs."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not resources:
            return []

        # Extract build IDs for batch operation
        build_ids = [resource.get("id", resource.get("Id", "")) for resource in resources]
        build_ids = [build_id for build_id in build_ids if build_id]

        if not build_ids:
            logger.warning("No valid build IDs found in resources")
            return []

        try:
            # Use batch_get_builds for efficient retrieval
            response = await self.client.batch_get_builds(ids=build_ids)
            builds = response.get("builds", [])
            
            logger.info(f"Successfully fetched details for {len(builds)} build runs")
            
            # Transform AWS response to our model format
            results = []
            for build in builds:
                transformed_build = {
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
                    "Tags": self._transform_tags(build.get("tags", []))
                }
                results.append(transformed_build)
            
            return results

        except Exception as e:
            logger.error(f"Error fetching build details: {e}")
            raise

    def _transform_tags(self, tags: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Transform AWS tags format to our expected format."""
        if not tags:
            return []
        
        transformed = []
        for tag in tags:
            if isinstance(tag, dict) and "key" in tag and "value" in tag:
                transformed.append({
                    "key": tag["key"],
                    "value": tag["value"]
                })
        return transformed


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