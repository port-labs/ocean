from typing import Dict, Any, List, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger
import asyncio


class GetDeploymentAction(Action[list[str]]):
    """Fetches detailed information about CodeDeploy deployments."""

    async def _execute(self, deployments: list[str]) -> List[Dict[str, Any]]:
        deployment_details = await asyncio.gather(
            *(self._fetch_deployment_details(deployment) for deployment in deployments),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, detail_result in enumerate(deployment_details):
            if isinstance(detail_result, dict):
                results.append(detail_result)
            else:
                results.append({})
                logger.error(f"Error fetching details for deployment '{deployments[idx]}': {detail_result}")
        return results

    async def _fetch_deployment_details(self, deployment: str) -> dict[str, Any]:
        """Fetch detailed information about a single deployment."""
        response = await self.client.get_deployment(deploymentId=deployment)
        logger.info(f"Successfully fetched details for deployment {deployment}")
        return response["deploymentInfo"]


class ListDeploymentsAction(Action[list[str]]):
    """Processes the initial list of deployments from AWS."""

    async def _execute(self, deployments: list[str]) -> list[Dict[str, Any]]:
        return [{"deploymentId": deployment} for deployment in deployments]


class CodeDeployDeploymentActionsMap(ActionMap[list[str]]):
    """Groups all actions for CodeDeploy Deployment resource type."""

    defaults: List[Type[Action[list[str]]]] = [
        GetDeploymentAction,
        ListDeploymentsAction,
    ]
    options: List[Type[Action[list[str]]]] = []
