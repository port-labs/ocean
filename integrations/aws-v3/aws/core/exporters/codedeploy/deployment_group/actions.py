from typing import Any, Type, cast, Dict, List, TypedDict
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import is_recoverable_aws_exception
from loguru import logger
import asyncio


class DeploymentGroupActionInput(TypedDict):
    app_name: str
    groups: list[str]
    extras: dict[str, str]


class GetDeploymentGroupDetailsAction(Action):
    """Fetches detailed information for CodeDeploy deployment groups."""

    async def _execute(self, groups_data: DeploymentGroupActionInput) -> List[Dict[str, Any]]:
        results = (await self.client.batch_get_deployment_groups(applicationName=groups_data["app_name"],
                                                                 deploymentGroupNames=groups_data["groups"])).get('deploymentGroupsInfo', [])
        logger.info(f"Successfully fetched details for {len(results)} CodeDeploy deployment groups")
        return results


class CodeDeployDeploymentGroupActionsMap(ActionMap):
    """Groups all actions for CodeDeploy deployment groups."""

    defaults: List[Type[Action]] = [
        GetDeploymentGroupDetailsAction,
    ]
    options: List[Type[Action]] = []
