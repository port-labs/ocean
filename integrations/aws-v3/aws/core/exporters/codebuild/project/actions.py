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

        return projects


class CodeBuildProjectActionsMap(ActionMap):
    """Groups all actions for CodeBuild project resource type."""

    defaults: List[Type[Action]] = [
        ListProjectsAction,
        GetProjectDetailsAction,
    ]
    options: List[Type[Action]] = []
