from aws.core.exporters.ecs.cluster.builder import (
    ECSClusterBuilder,
    ECSClusterBatchBuilder,
)
from aws.core.exporters.ecs.cluster.models import ECSCluster
from loguru import logger
from aws.core.exporters.ecs.cluster.actions import ECSClusterActionsMap
from typing import List, Dict, Any
from aiobotocore.client import AioBaseClient
import asyncio
from aws.core.interfaces.action import IAction, IBatchAction


class ECSClusterInspector:
    """A Facade for inspecting ECS clusters."""

    def __init__(self, client: AioBaseClient) -> None:
        self.client = client
        self.actions_map = ECSClusterActionsMap()

    async def inspect(self, cluster_arn: str, include: List[str]) -> ECSCluster:
        builder = ECSClusterBuilder(cluster_arn)
        action_classes = self.actions_map.merge(include)
        actions_to_run: List[IAction] = [
            action_cls(self.client) for action_cls in action_classes
        ]

        results = await asyncio.gather(
            *(self._run_action(action, cluster_arn) for action in actions_to_run)
        )

        for result in results:
            if result is not None:
                builder.with_data(result)

        cluster = builder.build()
        return cluster

    async def inspect_batch(
        self, cluster_arns: List[str], include: List[str]
    ) -> List[ECSCluster]:
        """Inspect multiple clusters efficiently using batch operations where possible"""
        if not cluster_arns:
            return []

        action_classes = self.actions_map.merge(include)
        actions_to_run: List[IAction] = [
            action_cls(self.client) for action_cls in action_classes
        ]

        batchable_actions = [
            action for action in actions_to_run if isinstance(action, IBatchAction)
        ]
        non_batchable_actions = [
            action for action in actions_to_run if not isinstance(action, IBatchAction)
        ]

        batch_builder = ECSClusterBatchBuilder(cluster_arns)

        if batchable_actions:
            batch_results = await asyncio.gather(
                *(
                    self._run_batch_action(action, cluster_arns)
                    for action in batchable_actions
                )
            )

            for result in batch_results:
                batch_builder.with_batch_data(result)

        if non_batchable_actions:
            individual_results = await asyncio.gather(
                *(
                    asyncio.gather(
                        *(self._run_action(action, arn) for arn in cluster_arns)
                    )
                    for action in non_batchable_actions
                )
            )

            for result in individual_results:
                batch_builder.with_batch_data(result)

        return batch_builder.build()

    async def _run_batch_action(
        self, action: IBatchAction, cluster_arns: List[str]
    ) -> List[Dict[str, Any]]:
        """Run a batchable action for multiple clusters"""
        try:
            return await action.execute_batch(cluster_arns)
        except Exception as e:
            logger.warning(f"{action.__class__.__name__} failed: {e}")
            return [{} for _ in cluster_arns]

    async def _run_action(self, action: IAction, cluster_arn: str) -> Dict[str, Any]:
        try:
            data = await action.execute(cluster_arn)
        except Exception as e:
            logger.warning(f"{action.__class__.__name__} failed: {e}")
            return {}
        return data
