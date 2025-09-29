from typing import Dict, Any, List, Type
from aws.core.interfaces.action import Action, ActionMap
from aws.core.exporters.ecs.utils import get_cluster_arn_from_service_arn
from loguru import logger


class ListServicesAction(Action):
    """List services as a pass-through function."""

    async def _execute(self, service_arns: List[str]) -> List[Dict[str, Any]]:
        """Return service ARNs as dictionaries"""
        return [{"serviceArn": arn} for arn in service_arns]


class DescribeServicesAction(Action):
    """Describes services with cluster context."""

    async def _execute(self, service_arns: List[str]) -> List[Dict[str, Any]]:
        cluster_arn = get_cluster_arn_from_service_arn(service_arns[0])

        response = await self.client.describe_services(
            cluster=cluster_arn, services=service_arns, include=["TAGS"]
        )
        logger.info(
            f"Successfully described {len(response['services'])} services for cluster '{cluster_arn}'"
        )
        return response["services"]


class EcsServiceActionsMap(ActionMap):
    defaults: List[Type[Action]] = [
        ListServicesAction,
        DescribeServicesAction,
    ]
    options: List[Type[Action]] = []
