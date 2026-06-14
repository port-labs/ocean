from typing import Any, Type, cast, Dict, List, TypedDict
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import is_recoverable_aws_exception
from loguru import logger
import asyncio


class DeploymentGroupActionInput(TypedDict):
    app_name: str
    groups: list[str]
    extras: dict[str, str]


class GetDeploymentGroupDetailsAction(Action):
    """Fetches detailed information for CodeDeploy deployment groups."""

    async def _execute(
        self, groups_data: DeploymentGroupActionInput
    ) -> List[Dict[str, Any]]:
        results = (
            await self.client.batch_get_deployment_groups(
                applicationName=groups_data["app_name"],
                deploymentGroupNames=groups_data["groups"],
            )
        ).get("deploymentGroupsInfo", [])
        logger.info(
            f"Successfully fetched details for {len(results)} CodeDeploy deployment groups"
        )
        return results


class GetDeploymentGroupTags(Action):
    async def _execute(
        self, groups_data: DeploymentGroupActionInput
    ) -> List[Dict[str, Any]]:
        tags = await asyncio.gather(
            *(
                self._fetch_tags(
                    app_name=groups_data["app_name"],
                    group_name=group,
                    region=groups_data["extras"]["region"],
                    account_id=groups_data["extras"]["account_id"],
                )
                for group in groups_data["groups"]
            ),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, tag_result in enumerate(tags):
            if isinstance(tag_result, Exception):
                logger.error(
                    f"Error fetching tags for DeploymentGroup '{groups_data['app_name']}/{groups_data['groups'][idx]}': {tag_result}"
                )
                results.append({})
                continue
            results.append(cast(Dict[str, Any], tag_result))
        return results

    async def _fetch_tags(
        self, app_name: str, group_name: str, region: str, account_id: str
    ) -> List[Dict[str, Any]]:
        arn = f"arn:aws:codedeploy:{region}:{account_id}:deploymentgroup:{app_name}/{group_name}"
        return await self.client.list_tags_for_resource(ResourceArn=arn)


class CodeDeployDeploymentGroupActionsMap(ActionMap):
    """Groups all actions for CodeDeploy deployment groups."""

    defaults: List[Type[Action]] = [
        GetDeploymentGroupDetailsAction,
        GetDeploymentGroupTags,
    ]
    options: List[Type[Action]] = []
