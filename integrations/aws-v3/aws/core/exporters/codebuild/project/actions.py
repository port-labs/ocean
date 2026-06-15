from typing import Dict, Any, List, Type
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger


class GetProjectDetailsAction(Action[list[str]]):
    """Fetches detailed information about CodeBuild projects."""

    async def _execute(self, resources: List[str]) -> List[Dict[str, Any]]:
        response = await self.client.batch_get_projects(names=resources)
        projects = response.get("projects", [])
        logger.info(f"Fetched details for {len(projects)} projects")

        return projects


class CodeBuildProjectActionsMap(ActionMap[list[str]]):
    """Groups all actions for CodeBuild project resource type."""

    defaults: List[Type[Action[list[str]]]] = [
        GetProjectDetailsAction,
    ]
    options: List[Type[Action[list[str]]]] = []
