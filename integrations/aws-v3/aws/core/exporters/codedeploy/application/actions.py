from typing import Dict, Any, List, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger
import asyncio


class GetCodeDeployApplicationDetailsAction(Action):
    """Fetches detailed information about CodeDeploy applications."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not resources:
            return []

        # Use batch operation for better performance
        application_names = [resource["ApplicationName"] for resource in resources]
        
        try:
            response = await self.client.batch_get_applications(
                applicationNames=application_names
            )
            
            logger.info(f"Successfully fetched details for {len(response.get('applicationsInfo', []))} CodeDeploy applications")
            
            results: List[Dict[str, Any]] = []
            for app_info in response.get("applicationsInfo", []):
                data = {
                    "ApplicationName": app_info.get("applicationName", ""),
                    "ApplicationId": app_info.get("applicationId", ""),
                    "CreateTime": app_info.get("createTime"),
                    "LinkedToGitHub": app_info.get("linkedToGitHub"),
                    "GitHubAccountName": app_info.get("gitHubAccountName"),
                    "ComputePlatform": app_info.get("computePlatform"),
                }
                results.append(data)
                
            return results
            
        except Exception as e:
            logger.error(f"Error fetching CodeDeploy application details: {e}")
            # Fallback to individual calls if batch fails
            details = await asyncio.gather(
                *(self._fetch_application_details(resource) for resource in resources),
                return_exceptions=True,
            )
            
            results: List[Dict[str, Any]] = []
            for idx, detail_result in enumerate(details):
                if isinstance(detail_result, Exception):
                    app_name = resources[idx].get("ApplicationName", "unknown")
                    logger.error(f"Error fetching details for application '{app_name}': {detail_result}")
                    continue
                results.append(cast(Dict[str, Any], detail_result))
            return results

    async def _fetch_application_details(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        response = await self.client.get_application(
            applicationName=resource["ApplicationName"]
        )
        
        app_info = response.get("application", {})
        logger.info(f"Successfully fetched details for CodeDeploy application {resource['ApplicationName']}")
        
        return {
            "ApplicationName": app_info.get("applicationName", ""),
            "ApplicationId": app_info.get("applicationId", ""),
            "CreateTime": app_info.get("createTime"),
            "LinkedToGitHub": app_info.get("linkedToGitHub"),
            "GitHubAccountName": app_info.get("gitHubAccountName"),
            "ComputePlatform": app_info.get("computePlatform"),
        }


class GetCodeDeployApplicationTagsAction(Action):
    """Fetches tags for CodeDeploy applications."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not resources:
            return []

        tags = await asyncio.gather(
            *(self._fetch_application_tags(resource) for resource in resources),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, tag_result in enumerate(tags):
            if isinstance(tag_result, Exception):
                app_name = resources[idx].get("ApplicationName", "unknown")
                logger.error(f"Error fetching tags for CodeDeploy application '{app_name}': {tag_result}")
                continue
            results.append(cast(Dict[str, Any], tag_result))
        return results

    async def _fetch_application_tags(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = await self.client.list_tags_for_resource(
                ResourceArn=f"arn:aws:codedeploy:{self.region}:{self.account_id}:application:{resource['ApplicationName']}"
            )
            return {"Tags": response.get("Tags", [])}
        except self.client.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code in ["ResourceNotFoundException", "InvalidParameterException"]:
                logger.info(f"No tags found for CodeDeploy application {resource['ApplicationName']}")
                return {"Tags": []}
            else:
                raise


class ListCodeDeployApplicationsAction(Action):
    """Processes the initial list of CodeDeploy applications."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for resource in resources:
            data = {
                "ApplicationName": resource["ApplicationName"],
            }
            results.append(data)
        return results


class CodeDeployApplicationActionsMap(ActionMap):
    """Groups all actions for CodeDeploy applications."""
    defaults: List[Type[Action]] = [
        GetCodeDeployApplicationDetailsAction,
        GetCodeDeployApplicationTagsAction,
        ListCodeDeployApplicationsAction,
    ]
    options: List[Type[Action]] = []