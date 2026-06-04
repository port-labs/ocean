from typing import Any, Type, cast, Dict, List
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import is_recoverable_aws_exception
from loguru import logger
import asyncio


class GetDeploymentGroupDetailsAction(Action):
    """Fetches detailed information for CodeDeploy deployment groups."""

    async def _execute(self, groups_data: list[Dict[str, str]]) -> List[Dict[str, Any]]:
        details = await asyncio.gather(
            *(self._fetch_deployment_group_details(group) for group in groups_data),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, detail_result in enumerate(details):
            if isinstance(detail_result, Exception):
                error_suffix = (f'deployment group details for {groups_data[idx].get("app_name", "unknown")}/'
                                f'{groups_data[idx].get("group_name", "unknown")}: {detail_result}')
                if is_recoverable_aws_exception(detail_result):
                    logger.warning(f"Skipping {error_suffix}")
                    continue
                else:
                    logger.error(f"Error fetching {error_suffix}")
                    raise detail_result
            results.append(cast(Dict[str, Any], detail_result))

        logger.info(f"Successfully fetched details for {len(results)} CodeDeploy deployment groups")
        return results

    async def _fetch_deployment_group_details(self, deployment_group: Dict[str, Any]) -> Dict[str, Any]:
        application_name = deployment_group["app_name"]
        deployment_group_name = deployment_group["group_name"]

        response = await self.client.get_deployment_group(
            applicationName=application_name,
            deploymentGroupName=deployment_group_name
        )

        logger.info(f"Successfully fetched details for deployment group {application_name}/{deployment_group_name}")

        deployment_group_info = response["deploymentGroupInfo"]

        return {
            "ApplicationName": deployment_group_info.get("applicationName", ""),
            "DeploymentGroupName": deployment_group_info.get("deploymentGroupName", ""),
            "DeploymentGroupId": deployment_group_info.get("deploymentGroupId", ""),
            "ServiceRoleArn": deployment_group_info.get("serviceRoleArn"),
            "AutoRollbackConfiguration": deployment_group_info.get("autoRollbackConfiguration"),
            "TriggerConfigurations": deployment_group_info.get("triggerConfigurations", []),
            "AlarmConfiguration": deployment_group_info.get("alarmConfiguration"),
            "OutdatedInstancesStrategy": deployment_group_info.get("outdatedInstancesStrategy"),
            "DeploymentStyle": deployment_group_info.get("deploymentStyle"),
            "BlueGreenDeploymentConfiguration": deployment_group_info.get("blueGreenDeploymentConfiguration"),
            "LoadBalancerInfo": deployment_group_info.get("loadBalancerInfo"),
            "LastSuccessfulDeployment": deployment_group_info.get("lastSuccessfulDeployment"),
            "LastAttemptedDeployment": deployment_group_info.get("lastAttemptedDeployment"),
            "Ec2TagFilters": deployment_group_info.get("ec2TagFilters", []),
            "OnPremisesInstanceTagFilters": deployment_group_info.get("onPremisesInstanceTagFilters", []),
            "AutoScalingGroups": deployment_group_info.get("autoScalingGroups", []),
            "Ec2TagSetList": deployment_group_info.get("ec2TagSetList", []),
            "OnPremisesTagSetList": deployment_group_info.get("onPremisesTagSetList", []),
            "EcsServices": deployment_group_info.get("ecsServices", []),
            "ComputePlatform": deployment_group_info.get("computePlatform"),
        }


class CodeDeployDeploymentGroupActionsMap(ActionMap):
    """Groups all actions for CodeDeploy deployment groups."""

    defaults: List[Type[Action]] = [
        GetDeploymentGroupDetailsAction,
    ]
    options: List[Type[Action]] = []
