from typing import Dict, Any, List, Type, cast, TypedDict
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger
import asyncio


class CodeDeployApplicationActionInput(TypedDict):
    applications: list[str]
    extras: dict[str, str]


class GetCodeDeployApplicationDetailsAction(Action):
    """Fetches detailed information about CodeDeploy applications."""

    async def _execute(self, resources: CodeDeployApplicationActionInput) -> List[Dict[str, Any]]:
        if not resources:
            return []

        response = (await self.client.batch_get_applications(applicationNames=resources['applications'])).get('applicationsInfo', [])

        logger.info(f"Successfully fetched details for {len(response)} CodeDeploy applications")
        return sorted(response, key=lambda app_info: app_info["applicationName"])


class GetCodeDeployApplicationTagsAction(Action):
    """Fetches tags for CodeDeploy applications."""

    async def _execute(self, resources: CodeDeployApplicationActionInput) -> List[Dict[str, Any]]:
        if not resources:
            return []

        tags = await asyncio.gather(
            *(self._fetch_application_tags(application, resources['extras']) for application in resources['applications']),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, tag_result in enumerate(tags):
            if isinstance(tag_result, Exception):
                app_name = resources['applications'][idx]
                logger.error(
                    f"Error fetching tags for CodeDeploy application '{app_name}': {tag_result}"
                )
                results.append({})
                continue
            results.append(cast(Dict[str, Any], tag_result))
        return results

    async def _fetch_application_tags(self, app_name: str, extras: dict[str, str]) -> Dict[str, Any]:
        app_arn = f"arn:aws:codedeploy:{extras['region']}:{extras['account_id']}:application:{app_name}"
        return await self.client.list_tags_for_resource(ResourceArn=app_arn)


class ListCodeDeployApplicationsAction(Action):
    """Processes the initial list of CodeDeploy applications."""

    async def _execute(self, resources: CodeDeployApplicationActionInput) -> List[Dict[str, Any]]:
        return [{"applicationName": app} for app in resources['applications']]


class CodeDeployApplicationActionsMap(ActionMap):
    """Groups all actions for CodeDeploy applications."""

    defaults: List[Type[Action]] = [
        GetCodeDeployApplicationDetailsAction,
        GetCodeDeployApplicationTagsAction,
        ListCodeDeployApplicationsAction,
    ]
    options: List[Type[Action]] = []
