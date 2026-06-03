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

        dg_info = response["deploymentGroupInfo"]

        return {
            "ApplicationName": dg_info.get("applicationName", ""),
            "DeploymentGroupName": dg_info.get("deploymentGroupName", ""),
            "DeploymentGroupId": dg_info.get("deploymentGroupId", ""),
            "ServiceRoleArn": dg_info.get("serviceRoleArn"),
            "AutoRollbackConfiguration": dg_info.get("autoRollbackConfiguration"),
            "TriggerConfigurations": dg_info.get("triggerConfigurations", []),
            "AlarmConfiguration": dg_info.get("alarmConfiguration"),
            "OutdatedInstancesStrategy": dg_info.get("outdatedInstancesStrategy"),
            "DeploymentStyle": dg_info.get("deploymentStyle"),
            "BlueGreenDeploymentConfiguration": dg_info.get("blueGreenDeploymentConfiguration"),
            "LoadBalancerInfo": dg_info.get("loadBalancerInfo"),
            "LastSuccessfulDeployment": dg_info.get("lastSuccessfulDeployment"),
            "LastAttemptedDeployment": dg_info.get("lastAttemptedDeployment"),
            "Ec2TagFilters": dg_info.get("ec2TagFilters", []),
            "OnPremisesInstanceTagFilters": dg_info.get("onPremisesInstanceTagFilters", []),
            "AutoScalingGroups": dg_info.get("autoScalingGroups", []),
            "Ec2TagSetList": dg_info.get("ec2TagSetList", []),
            "OnPremisesTagSetList": dg_info.get("onPremisesTagSetList", []),
            "EcsServices": dg_info.get("ecsServices", []),
            "ComputePlatform": dg_info.get("computePlatform"),
        }


class CodeDeployDeploymentGroupActionsMap(ActionMap):
    """Groups all actions for CodeDeploy deployment groups."""

    defaults: List[Type[Action]] = [
        GetDeploymentGroupDetailsAction,
    ]
    options: List[Type[Action]] = []
