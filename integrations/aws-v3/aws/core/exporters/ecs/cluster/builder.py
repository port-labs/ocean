from aws.core.exporters.ecs.cluster.models import ECSCluster, ECSClusterProperties
from typing import Dict, Any, Self, List


class ECSClusterBuilder:
    def __init__(self, cluster_arn: str) -> None:
        self._cluster = ECSCluster(
            Properties=ECSClusterProperties(clusterArn=cluster_arn)
        )

    def with_data(self, data: Dict[str, Any]) -> Self:
        for key, value in data.items():
            setattr(self._cluster.Properties, key, value)
        return self

    def build(self) -> ECSCluster:
        return self._cluster


class ECSClusterBatchBuilder:
    """Builder for efficiently constructing multiple ECS clusters from batch action results"""

    def __init__(self, cluster_arns: List[str]) -> None:
        self.cluster_arns = cluster_arns
        self.builders = [ECSClusterBuilder(arn) for arn in cluster_arns]

    def with_batch_data(self, action_results: List[Dict[str, Any]]) -> Self:
        """Add data from a batch action to all clusters"""
        for builder, result in zip(self.builders, action_results):
            if result is not None:
                builder.with_data(result)
        return self

    def build(self) -> List[ECSCluster]:
        """Build all clusters"""
        return [builder.build() for builder in self.builders]
