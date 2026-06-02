from typing import Dict, Any, List, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger
import asyncio


class GetCodeDeployApplicationDetailsAction(Action):
    """Fetches detailed information about CodeDeploy applications."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not resources:
            return []

        response = await self.client.batch_get_applications(
            applicationNames=[resource["applicationName"] for resource in resources]
        )

        logger.info(
            f"Successfully fetched details for {len(response.get('applicationsInfo', []))} CodeDeploy applications"
        )

        return sorted(
            [
                {
                    "ApplicationName": app_info.get("applicationName", ""),
                    "ApplicationId": app_info.get("applicationId", ""),
                    "CreateTime": app_info.get("createTime"),
                    "LinkedToGitHub": app_info.get("linkedToGitHub"),
                    "GitHubAccountName": app_info.get("gitHubAccountName"),
                    "ComputePlatform": app_info.get("computePlatform"),
                }
                for app_info in response.get("applicationsInfo", [])
            ],
            key=lambda app_info: app_info["ApplicationName"],
        )


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
                app_name = resources[idx].get("applicationName", "unknown")
                logger.error(
                    f"Error fetching tags for CodeDeploy application '{app_name}': {tag_result}"
                )
                continue
            results.append(cast(Dict[str, Any], tag_result))
        return results

    async def _fetch_application_tags(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = await self.client.list_tags_for_resource(
                ResourceArn=f"arn:aws:codedeploy:{resource['region']}:{resource['accountId']}:application:{resource['applicationName']}"
            )
            return {"Tags": response.get("Tags", [])}
        except self.client.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code in ["ResourceNotFoundException", "InvalidParameterException"]:
                logger.info(
                    f"No tags found for CodeDeploy application {resource['applicationName']}"
                )
                return {"Tags": []}
            else:
                raise


class ListCodeDeployApplicationsAction(Action):
    """Processes the initial list of CodeDeploy applications."""

    async def _execute(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {"ApplicationName": resource["applicationName"]} for resource in resources
        ]


class CodeDeployApplicationActionsMap(ActionMap):
    """Groups all actions for CodeDeploy applications."""

    defaults: List[Type[Action]] = [
        GetCodeDeployApplicationDetailsAction,
        GetCodeDeployApplicationTagsAction,
        ListCodeDeployApplicationsAction,
    ]
    options: List[Type[Action]] = []
