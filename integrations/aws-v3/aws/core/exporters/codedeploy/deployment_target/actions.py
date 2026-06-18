from dataclasses import dataclass
from typing import Any, Dict, List, Type
from aws.core.interfaces.action import Action, ActionMap, BaseActionInput
from loguru import logger


@dataclass
class DeploymentTargetActionInput(BaseActionInput[str]):
    deployment_id: str
    account_id: str
    region: str


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
        # Normalize: inject DeploymentId and flatten the nested target type dict
        normalized: List[Dict[str, Any]] = []
        for target in results:
            entry: Dict[str, Any] = {"DeploymentId": targets_data.deployment_id}
            target_type = target.get("deploymentTargetType", "")
            entry["DeploymentTargetType"] = target_type

            # Map from AWS API snake_case keys to PascalCase model keys
            type_key_map = {
                "instanceTarget": "InstanceTarget",
                "lambdaTarget": "LambdaTarget",
                "ecsTarget": "EcsTarget",
                "cloudFormationTarget": "CloudFormationTarget",
            }
            target_id = ""
            status = None
            last_updated_at = None
            lifecycle_events: List[Dict[str, Any]] = []
            target_arn = None

            for snake_key, pascal_key in type_key_map.items():
                nested = target.get(snake_key)
                if nested:
                    entry[pascal_key] = nested
                    target_id = nested.get("targetId", "")
                    target_arn = nested.get("targetArn")
                    status = nested.get("status")
                    last_updated_at = nested.get("lastUpdatedAt")
                    lifecycle_events = nested.get("lifecycleEvents", [])

            entry["TargetId"] = target_id
            if target_arn is not None:
                entry["TargetArn"] = target_arn
            if status is not None:
                entry["Status"] = status
            if last_updated_at is not None:
                entry["LastUpdatedAt"] = str(last_updated_at)
            entry["LifecycleEvents"] = lifecycle_events

            normalized.append(entry)
        return normalized


class CodeDeployDeploymentTargetActionsMap(ActionMap[DeploymentTargetActionInput]):
    """Groups all actions for CodeDeploy deployment targets."""

    defaults: List[Type[Action[DeploymentTargetActionInput]]] = [
        GetDeploymentTargetDetailsAction,
    ]
    options: List[Type[Action[DeploymentTargetActionInput]]] = []
