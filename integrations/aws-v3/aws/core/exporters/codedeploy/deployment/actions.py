from typing import Dict, Any, List, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger
import asyncio


class GetDeploymentAction(Action):
    """Fetches detailed information about CodeDeploy deployments."""

    async def _execute(self, deployments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not deployments:
            return []

        deployment_details = await asyncio.gather(
            *(self._fetch_deployment_details(deployment) for deployment in deployments),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, detail_result in enumerate(deployment_details):
            if isinstance(detail_result, Exception):
                deployment_id = deployments[idx].get("deploymentId", "unknown")
                logger.error(
                    f"Error fetching details for deployment '{deployment_id}': {detail_result}"
                )
                continue
            results.append(cast(Dict[str, Any], detail_result))
        return results

    async def _fetch_deployment_details(
        self, deployment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fetch detailed information about a single deployment."""
        response = await self.client.get_deployment(
            deploymentId=deployment["deploymentId"]
        )

        deployment_info = response["deploymentInfo"]
        logger.info(
            f"Successfully fetched details for deployment {deployment['deploymentId']}"
        )

        return {
            "ApplicationName": deployment_info.get("applicationName"),
            "DeploymentGroupName": deployment_info.get("deploymentGroupName"),
            "DeploymentId": deployment_info.get("deploymentId"),
            "Status": deployment_info.get("status"),
            "ErrorInformation": deployment_info.get("errorInformation"),
            "CreateTime": deployment_info.get("createTime"),
            "StartTime": deployment_info.get("startTime"),
            "CompleteTime": deployment_info.get("completeTime"),
            "DeploymentOverview": deployment_info.get("deploymentOverview"),
            "Description": deployment_info.get("description"),
            "Creator": deployment_info.get("creator"),
            "IgnoreApplicationStopFailures": deployment_info.get(
                "ignoreApplicationStopFailures"
            ),
            "AutoRollbackConfiguration": deployment_info.get(
                "autoRollbackConfiguration"
            ),
            "UpdateOutdatedInstancesOnly": deployment_info.get(
                "updateOutdatedInstancesOnly"
            ),
            "RollbackInfo": deployment_info.get("rollbackInfo"),
            "DeploymentStyle": deployment_info.get("deploymentStyle"),
            "TargetInstances": deployment_info.get("targetInstances"),
            "InstanceTerminationWaitTimeStarted": deployment_info.get(
                "instanceTerminationWaitTimeStarted"
            ),
            "BlueGreenDeploymentConfiguration": deployment_info.get(
                "blueGreenDeploymentConfiguration"
            ),
            "LoadBalancerInfo": deployment_info.get("loadBalancerInfo"),
            "AdditionalDeploymentStatusInfo": deployment_info.get(
                "additionalDeploymentStatusInfo"
            ),
            "FileExistsBehavior": deployment_info.get("fileExistsBehavior"),
            "ExternalId": deployment_info.get("externalId"),
            "Revision": deployment_info.get("revision"),
        }


class ListDeploymentsAction(Action):
    """Processes the initial list of deployments from AWS."""

    async def _execute(self, deployments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for deployment in deployments:
            data = {
                "deploymentId": deployment["deploymentId"],
                # Basic deployment information that might be available from list operation
            }
            results.append(data)
        return results


class CodeDeployDeploymentActionsMap(ActionMap):
    """Groups all actions for CodeDeploy Deployment resource type."""

    defaults: List[Type[Action]] = [
        GetDeploymentAction,
        ListDeploymentsAction,
    ]
    options: List[Type[Action]] = [
        # Add optional actions here if needed in the future
    ]
