from dataclasses import dataclass
from typing import Dict, Any, List, Type, cast
from aws.core.interfaces.action import Action, ActionMap, BaseActionInput
from loguru import logger
import asyncio


@dataclass
class CodeDeployApplicationActionInput(BaseActionInput[str]):
    region: str
    account_id: str


class GetCodeDeployApplicationDetailsAction(Action[CodeDeployApplicationActionInput]):
    """Fetches detailed information about CodeDeploy applications."""

    async def _execute(
        self, resources: CodeDeployApplicationActionInput
    ) -> List[Dict[str, Any]]:
        response = (
            await self.client.batch_get_applications(
                applicationNames=resources.items,
            )
        ).get("applicationsInfo", [])

        logger.info(
            f"Successfully fetched details for {len(response)} CodeDeploy applications"
        )
        return sorted(response, key=lambda app_info: app_info["applicationName"])


class GetCodeDeployApplicationTagsAction(Action[CodeDeployApplicationActionInput]):
    """Fetches tags for CodeDeploy applications."""

    async def _execute(
        self, resources: CodeDeployApplicationActionInput
    ) -> List[Dict[str, Any]]:
        tags = await asyncio.gather(
            *(
                self._fetch_application_tags(
                    application, resources.region, resources.account_id
                )
                for application in resources.items
            ),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, tag_result in enumerate(tags):
            if isinstance(tag_result, Exception):
                logger.error(
                    f"Error fetching tags for CodeDeploy application '{resources.items[idx]}': {tag_result}"
                )
                results.append({})
                continue
            results.append(cast(Dict[str, Any], tag_result))
        return results

    async def _fetch_application_tags(
        self, app_name: str, region: str, account_id: str
    ) -> Dict[str, Any]:
        app_arn = f"arn:aws:codedeploy:{region}:{account_id}:application:{app_name}"
        return await self.client.list_tags_for_resource(ResourceArn=app_arn)


class CodeDeployApplicationActionsMap(ActionMap[CodeDeployApplicationActionInput]):
    """Groups all actions for CodeDeploy applications."""

    defaults: List[Type[Action[CodeDeployApplicationActionInput]]] = [
        GetCodeDeployApplicationDetailsAction,
        GetCodeDeployApplicationTagsAction,
    ]
    options: List[Type[Action[CodeDeployApplicationActionInput]]] = []
