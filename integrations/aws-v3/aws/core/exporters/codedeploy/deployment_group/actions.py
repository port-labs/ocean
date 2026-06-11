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
        details = await asyncio.gather(
            *(self._fetch_deployment_group_details(app_name=groups_data['app_name'], group_name=group) for group in groups_data['groups']),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, detail_result in enumerate(details):
            if isinstance(detail_result, Exception):
                error_suffix = f'deployment group details for {groups_data["app_name"]}/{groups_data['groups'][idx]}: {detail_result}'
                logger.warning(f"Skipping {error_suffix}")
                results.append({})
            else:
                results.append(cast(Dict[str, Any], detail_result))

        logger.info(f"Successfully fetched details for {len(results)} CodeDeploy deployment groups")
        return results

    async def _fetch_deployment_group_details(self, app_name: str, group_name: str) -> Dict[str, Any]:
        response = await self.client.get_deployment_group(
            applicationName=app_name,
            deploymentGroupName=group_name
        )

        logger.info(f"Successfully fetched details for deployment group {app_name}/{group_name}")
        return response.get('deploymentGroupInfo', {})


class CodeDeployDeploymentGroupActionsMap(ActionMap):
    """Groups all actions for CodeDeploy deployment groups."""

    defaults: List[Type[Action]] = [
        GetDeploymentGroupDetailsAction,
    ]
    options: List[Type[Action]] = []
