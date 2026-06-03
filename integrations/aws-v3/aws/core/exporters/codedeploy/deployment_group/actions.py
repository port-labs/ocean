from typing import Any, Type, cast, Dict, List
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import is_recoverable_aws_exception
from loguru import logger
import asyncio


class GetDeploymentGroupDetailsAction(Action):
    """Fetches detailed information for CodeDeploy deployment groups."""

    async def _execute(self, applications: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        if not applications:
            return []

        app_to_groups = await asyncio.gather(
            *(self._fetch_deployment_group_names_of_app(app["app_name"]) for app in applications),
            return_exceptions=True,
        )
        group_data = [group for app_grouping in app_to_groups for group in app_grouping if app_grouping]

        details = await asyncio.gather(
            *(self._fetch_deployment_group_details(group) for group in group_data),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, detail_result in enumerate(details):
            if isinstance(detail_result, Exception):
                dg_name = group_data[idx].get("app_name", "unknown")
                app_name = group_data[idx].get("group_name", "unknown")
                if is_recoverable_aws_exception(detail_result):
                    logger.warning(
                        f"Skipping deployment group details for '{app_name}/{dg_name}': {detail_result}"
                    )
                    continue
                else:
                    logger.error(
                        f"Error fetching deployment group details for '{app_name}/{dg_name}': {detail_result}"
                    )
                    raise detail_result
            results.append(cast(Dict[str, Any], detail_result))

        logger.info(f"Successfully fetched details for {len(results)} CodeDeploy deployment groups")
        return results

    async def _fetch_deployment_group_names_of_app(self, app_name: str) -> list[dict[str, str]]:
        response = await self.client.list_deployment_groups(applicationName=app_name)
        return [{'app_name': app_name, 'group_name': group} for group in response.get("deploymentGroups", [])]

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
