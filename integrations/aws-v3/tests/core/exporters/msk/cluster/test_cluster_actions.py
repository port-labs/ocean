from typing import Any
from unittest.mock import AsyncMock

import pytest

from aws.core.exporters.msk.cluster.actions import (
    ListClustersAction,
    MskClusterActionsMap,
)
from aws.core.interfaces.action import Action


class TestListClustersAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> ListClustersAction:
        return ListClustersAction(mock_client)

    def test_inheritance(self, action: ListClustersAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_returns_clusters_as_is(
        self, action: ListClustersAction
    ) -> None:
        clusters: list[dict[str, Any]] = [
            {
                "ClusterArn": "arn:aws:kafka:us-west-2:123456789012:cluster/cluster1/abc",
                "ClusterName": "cluster1",
                "State": "ACTIVE",
                "NumberOfBrokerNodes": 3,
                "BrokerNodeGroupInfo": {"InstanceType": "kafka.m5.large"},
            },
            {
                "ClusterArn": "arn:aws:kafka:us-west-2:123456789012:cluster/cluster2/def",
                "ClusterName": "cluster2",
                "State": "CREATING",
                "NumberOfBrokerNodes": 3,
            },
        ]

        result = await action.execute(clusters)

        assert result == clusters
        assert len(result) == 2


class TestMskClusterActionsMap:

    def test_defaults(self) -> None:
        assert ListClustersAction in MskClusterActionsMap.defaults

    def test_options_empty(self) -> None:
        assert MskClusterActionsMap.options == []
