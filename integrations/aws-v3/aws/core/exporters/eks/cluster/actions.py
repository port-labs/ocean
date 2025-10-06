import asyncio
from typing import Dict, Any, List, Type, cast
from loguru import logger
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import is_recoverable_aws_exception


class DescribeClusterAction(Action):
    async def _execute(self, cluster_names: List[str]) -> List[Dict[str, Any]]:

        cluster_results = await asyncio.gather(
            *(self._fetch_cluster(name) for name in cluster_names),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, result in enumerate(cluster_results):
            if isinstance(result, Exception):
                cluster_name = (
                    cluster_names[idx] if idx < len(cluster_names) else "unknown"
                )
                if is_recoverable_aws_exception(result):
                    logger.warning(
                        f"Skipping EKS cluster '{cluster_name}' due to error: {result}"
                    )
                    continue
                else:
                    logger.error(f"Error fetching EKS cluster '{cluster_name}'")
                    raise result
            results.append(cast(Dict[str, Any], result))

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
