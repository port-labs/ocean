from typing import Dict, Any, List, Type
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger


class ListBuildsAction(Action[list[str]]):
    """Processes the initial list of build runs from AWS."""

    async def _execute(self, resources: list[str]) -> List[Dict[str, Any]]:
        return [{"id": build_id} for build_id in resources]


class GetBuildDetailsAction(Action[list[str]]):
    """Fetches detailed information about CodeBuild project build runs."""

    async def _execute(self, resources: list[str]) -> List[Dict[str, Any]]:
        response = await self.client.batch_get_builds(ids=resources)
        builds = response.get("builds", [])
        logger.info(f"Successfully fetched details for {len(builds)} build runs")
        return builds


class BuildRunActionsMap(ActionMap[list[str]]):
    """Groups all actions for CodeBuild project build runs."""

    defaults: List[Type[Action[list[str]]]] = [
        GetBuildDetailsAction,
        ListBuildsAction,
    ]
    options: List[Type[Action[list[str]]]] = []
