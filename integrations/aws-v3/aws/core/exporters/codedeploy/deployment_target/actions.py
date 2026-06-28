from dataclasses import dataclass
from typing import Any, Dict, List, Type
from aws.core.interfaces.action import Action, ActionMap, BaseActionInput
from loguru import logger


@dataclass
class DeploymentTargetActionInput(BaseActionInput[str]):
    deployment_id: str


class GetDeploymentTargetDetailsAction(Action[DeploymentTargetActionInput]):
    """Fetches detailed information for CodeDeploy deployment targets."""

    async def _execute(
        self, targets_data: DeploymentTargetActionInput
    ) -> List[Dict[str, Any]]:
        results = (
            await self.client.batch_get_deployment_targets(
                deploymentId=targets_data.deployment_id,
                targetIds=targets_data.items,
            )
        ).get("deploymentTargets", [])
        logger.info(
            f"Successfully fetched details for {len(results)} CodeDeploy deployment targets"
        )
        return [
            {**result, 'deploymentId': targets_data.deployment_id}
            for result in results
        ]


class CodeDeployDeploymentTargetActionsMap(ActionMap[DeploymentTargetActionInput]):
    """Groups all actions for CodeDeploy deployment targets."""

    defaults: List[Type[Action[DeploymentTargetActionInput]]] = [
        GetDeploymentTargetDetailsAction,
    ]
    options: List[Type[Action[DeploymentTargetActionInput]]] = []
