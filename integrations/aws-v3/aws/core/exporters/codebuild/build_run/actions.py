from typing import Dict, Any, List, Type
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger


class ListBuildsAction(Action):
    """Processes the initial list of build runs from AWS."""

    async def _execute(self, resources: list[str]) -> List[Dict[str, Any]]:
        return [{"id": build_id} for build_id in resources]


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
        return builds


class BuildRunActionsMap(ActionMap):
    """Groups all actions for CodeBuild project build runs."""

    defaults: List[Type[Action]] = [
        GetBuildDetailsAction,
        ListBuildsAction,
    ]
    options: List[Type[Action]] = []
