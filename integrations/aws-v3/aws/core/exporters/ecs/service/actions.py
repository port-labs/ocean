from typing import Dict, Any, List, Type
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger


class ListServicesAction(Action):
    """List services as a pass-through function."""

    async def _execute(
        self, service_identifiers: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Return services as is"""
        return service_identifiers


class DescribeServicesAction(Action):
    """Describes services with cluster context."""

    async def _execute(
        self, service_identifiers: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        cluster_arn = service_identifiers[0]["clusterArn"]
        service_arns = [
            service_info["serviceArn"] for service_info in service_identifiers
        ]

        try:
            response = await self.client.describe_services(
                cluster=cluster_arn, services=service_arns, include=["TAGS"]
            )
            logger.info(
                f"Successfully described {len(response['services'])} services for cluster '{cluster_arn}'"
            )
            return response["services"]
        except Exception as e:
            logger.error(f"Error describing services for cluster '{cluster_arn}': {e}")
            return []


class EcsServiceActionsMap(ActionMap):
    defaults: List[Type[Action]] = [
        ListServicesAction,
        DescribeServicesAction,
    ]
    options: List[Type[Action]] = []
