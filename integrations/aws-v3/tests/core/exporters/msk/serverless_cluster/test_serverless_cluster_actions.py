import pytest
from typing import Any
from unittest.mock import AsyncMock
from aws.core.exporters.msk.serverless_cluster.actions import (
    ListMskServerlessClustersAction,
    MskServerlessClusterActionsMap,
)

SAMPLE_CLUSTERS: list[dict[str, Any]] = [
    {
        "ClusterArn": "arn:aws:kafka:us-east-1:123456789012:cluster/cluster-a/abc",
        "ClusterName": "cluster-a",
        "ClusterType": "SERVERLESS",
        "State": "ACTIVE",
        "Tags": {"env": "prod"},
        "Serverless": {
            "VpcConfigs": [{"SubnetIds": ["subnet-1"], "SecurityGroupIds": ["sg-1"]}],
            "ClientAuthentication": {"Sasl": {"Iam": {"Enabled": True}}},
        },
    },
    {
        "ClusterArn": "arn:aws:kafka:us-east-1:123456789012:cluster/cluster-b/def",
        "ClusterName": "cluster-b",
        "ClusterType": "SERVERLESS",
        "State": "CREATING",
    },
]


class TestListMskServerlessClustersAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> ListMskServerlessClustersAction:
        return ListMskServerlessClustersAction(mock_client)

    @pytest.mark.asyncio
    async def test_pass_through_returns_clusters_unchanged(
        self, action: ListMskServerlessClustersAction
    ) -> None:
        result = await action._execute(SAMPLE_CLUSTERS)
        assert result == SAMPLE_CLUSTERS

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty_list(
        self, action: ListMskServerlessClustersAction
    ) -> None:
        result = await action._execute([])
        assert result == []

    @pytest.mark.asyncio
    async def test_no_aws_calls_made(
        self, action: ListMskServerlessClustersAction, mock_client: AsyncMock
    ) -> None:
        await action._execute(SAMPLE_CLUSTERS)
        mock_client.assert_not_awaited()


class TestMskServerlessClusterActionsMap:

    def test_defaults_contains_list_action(self) -> None:
        actions_map = MskServerlessClusterActionsMap()
        assert ListMskServerlessClustersAction in actions_map.defaults

    def test_options_is_empty(self) -> None:
        actions_map = MskServerlessClusterActionsMap()
        assert actions_map.options == []

    def test_merge_returns_only_defaults_when_no_include(self) -> None:
        actions_map = MskServerlessClusterActionsMap()
        merged = actions_map.merge([])
        assert merged == [ListMskServerlessClustersAction]
