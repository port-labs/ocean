import asyncio
from typing import Any, Dict, List, Type, TypedDict, cast
from loguru import logger
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import is_recoverable_aws_exception


class NodegroupRecord(TypedDict):
    clusterName: str
    nodegroupName: str


class DescribeNodegroupAction(Action[list[NodegroupRecord]]):
    async def _execute(self, nodegroups: List[NodegroupRecord]) -> List[Dict[str, Any]]:
        """Fetch detailed information for each EKS nodegroup."""

        nodegroup_results = await asyncio.gather(
            *(self._fetch_nodegroup(record) for record in nodegroups),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, result in enumerate(nodegroup_results):
            if isinstance(result, Exception):
                record = nodegroups[idx]
                nodegroup_id = f"{record['clusterName']}/{record['nodegroupName']}"
                if is_recoverable_aws_exception(result):
                    logger.warning(
                        f"Skipping EKS nodegroup '{nodegroup_id}' due to error: {result}"
                    )
                    continue
                else:
                    logger.error(
                        f"Error fetching EKS nodegroup '{nodegroup_id}': {result}"
                    )
                    raise result
            results.append(cast(Dict[str, Any], result))

        return results

    async def _fetch_nodegroup(self, record: NodegroupRecord) -> Dict[str, Any]:
        """Fetch a single nodegroup by cluster name and nodegroup name."""
        response = await self.client.describe_nodegroup(
            clusterName=record["clusterName"],
            nodegroupName=record["nodegroupName"],
        )
        logger.info(
            f"Successfully fetched EKS nodegroup '{record['nodegroupName']}' "
            f"in cluster '{record['clusterName']}'"
        )
        return response["nodegroup"]


class EksNodegroupActionsMap(ActionMap[list[NodegroupRecord]]):
    defaults: List[Type[Action[list[NodegroupRecord]]]] = [
        DescribeNodegroupAction,
    ]
    options: List[Type[Action[list[NodegroupRecord]]]] = []
