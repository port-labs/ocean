from typing import Any, Type, cast, Dict, List
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import is_recoverable_aws_exception
from loguru import logger
import asyncio


class GetDeploymentGroupDetailsAction(Action):
    """Fetches detailed information for CodeDeploy deployment groups."""

    async def _execute(self, deployment_groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not deployment_groups:
            return []

        details = await asyncio.gather(
            *(self._fetch_deployment_group_details(dg) for dg in deployment_groups),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, detail_result in enumerate(details):
            if isinstance(detail_result, Exception):
                dg_name = deployment_groups[idx].get("DeploymentGroupName", "unknown")
                app_name = deployment_groups[idx].get("ApplicationName", "unknown")
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

    async def _fetch_deployment_group_details(self, deployment_group: Dict[str, Any]) -> Dict[str, Any]:
        application_name = deployment_group["ApplicationName"]
        deployment_group_name = deployment_group["DeploymentGroupName"]
        
        response = await self.client.get_deployment_group(
            applicationName=application_name,
            deploymentGroupName=deployment_group_name
        )
        
        logger.info(f"Successfully fetched details for deployment group {application_name}/{deployment_group_name}")
        
        # Extract the deployment group info from the response
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


class ListDeploymentGroupTagsAction(Action):
    """Lists tags for CodeDeploy deployment groups."""

    async def _execute(self, deployment_groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not deployment_groups:
            return []

        tags = await asyncio.gather(
            *(self._fetch_deployment_group_tags(dg) for dg in deployment_groups),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, tag_result in enumerate(tags):
            if isinstance(tag_result, Exception):
                dg_name = deployment_groups[idx].get("DeploymentGroupName", "unknown")
                app_name = deployment_groups[idx].get("ApplicationName", "unknown")
                if is_recoverable_aws_exception(tag_result):
                    logger.warning(
                        f"Skipping tags for deployment group '{app_name}/{dg_name}': {tag_result}"
                    )
                    # Return empty tags for this deployment group
                    results.append({"Tags": []})
                    continue
                else:
                    logger.error(
                        f"Error fetching tags for deployment group '{app_name}/{dg_name}': {tag_result}"
                    )
                    raise tag_result
            results.append(cast(Dict[str, Any], tag_result))
        
        logger.info(f"Successfully fetched tags for {len(results)} CodeDeploy deployment groups")
        return results

    async def _fetch_deployment_group_tags(self, deployment_group: Dict[str, Any]) -> Dict[str, Any]:
        application_name = deployment_group["ApplicationName"]
        deployment_group_name = deployment_group["DeploymentGroupName"]
        
        # Get the deployment group info to get the ARN for tag listing
        dg_response = await self.client.get_deployment_group(
            applicationName=application_name,
            deploymentGroupName=deployment_group_name
        )
        
        # Extract the deployment group ARN 
        dg_info = dg_response["deploymentGroupInfo"]
        service_role_arn = dg_info.get("serviceRoleArn", "")
        
        # Unfortunately, CodeDeploy doesn't have a direct list_tags_for_resource for deployment groups
        # We'll return empty tags for now, but this could be enhanced if needed
        logger.info(f"Tags not directly available for deployment group {application_name}/{deployment_group_name}")
        
        return {"Tags": []}


class ListApplicationsAndDeploymentGroupsAction(Action):
    """Lists all applications and their deployment groups."""

    async def _execute(self, applications: List[str]) -> List[Dict[str, Any]]:
        """Process the list of application names and return deployment group info."""
        if not applications:
            return []

        all_deployment_groups = []
        
        for app_name in applications:
            try:
                # List deployment groups for this application
                response = await self.client.list_deployment_groups(applicationName=app_name)
                deployment_groups = response.get("deploymentGroups", [])
                
                # Create deployment group info objects
                for dg_name in deployment_groups:
                    all_deployment_groups.append({
                        "ApplicationName": app_name,
                        "DeploymentGroupName": dg_name,
                    })
                
                logger.info(f"Found {len(deployment_groups)} deployment groups in application {app_name}")
                
            except Exception as e:
                if is_recoverable_aws_exception(e):
                    logger.warning(f"Skipping application '{app_name}': {e}")
                    continue
                else:
                    logger.error(f"Error listing deployment groups for application '{app_name}': {e}")
                    raise e

        logger.info(f"Successfully listed {len(all_deployment_groups)} deployment groups across all applications")
        return all_deployment_groups


class CodeDeployDeploymentGroupActionsMap(ActionMap):
    """Groups all actions for CodeDeploy deployment groups."""
    
    defaults: List[Type[Action]] = [
        ListApplicationsAndDeploymentGroupsAction,
        GetDeploymentGroupDetailsAction,
    ]
    options: List[Type[Action]] = [
        ListDeploymentGroupTagsAction,
    ]