import asyncio
from typing import Dict, Any, List, Type
from loguru import logger
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import is_recoverable_aws_exception


class DescribeClusterAction(Action):
    async def _execute(self, cluster_names: List[str]) -> List[Dict[str, Any]]:
        if not cluster_names:
            return []

        cluster_results = await asyncio.gather(
            *(self._fetch_cluster(name) for name in cluster_names),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for result in cluster_results:
            if isinstance(result, Exception):
                if is_recoverable_aws_exception(result):
                    logger.warning(
                        f"Skipping EKS cluster due to recoverable e rror: {result}"
                    )
                else:
                    raise result
            else:
                results.append(result)

        return results

    async def _fetch_cluster(self, cluster_name: str) -> Dict[str, Any]:
        """Fetch a single cluster by name."""
        response = await self.client.describe_cluster(name=cluster_name)
        logger.info(f"Successfully fetched EKS cluster '{cluster_name}'")
        return response["cluster"]


class EksClusterActionsMap(ActionMap):
    defaults: List[Type[Action]] = [
        DescribeClusterAction,
    ]
    options: List[Type[Action]] = []
