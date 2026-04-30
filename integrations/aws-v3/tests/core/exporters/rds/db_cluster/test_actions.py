from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.rds.db_cluster.actions import (
    DescribeDBClustersAction,
    ListTagsForResourceAction,
    RdsDbClusterActionsMap,
)
from aws.core.interfaces.action import Action


class TestDescribeDBClustersAction:

    @pytest.fixture
    def action(self) -> DescribeDBClustersAction:
        return DescribeDBClustersAction(AsyncMock())

    def test_inheritance(self, action: DescribeDBClustersAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_returns_input(
        self, action: DescribeDBClustersAction
    ) -> None:
        """Test that the pass-through action returns the input as-is."""
        db_clusters = [
            {
                "DBClusterIdentifier": "cluster-1",
                "DBClusterArn": "arn:aws:rds:us-east-1:123456789012:cluster:cluster-1",
            },
            {
                "DBClusterIdentifier": "cluster-2",
                "DBClusterArn": "arn:aws:rds:us-east-1:123456789012:cluster:cluster-2",
            },
        ]
        result = await action.execute(db_clusters)
        assert result == db_clusters


class TestListTagsForResourceAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        client = AsyncMock()
        client.list_tags_for_resource = AsyncMock()
        return client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> ListTagsForResourceAction:
        return ListTagsForResourceAction(mock_client)

    def test_inheritance(self, action: ListTagsForResourceAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.rds.db_cluster.actions.logger")
    async def test_execute_success(
        self, mock_logger: MagicMock, action: ListTagsForResourceAction
    ) -> None:
        """Test successful execution of list_tags_for_resource."""
        db_clusters = [
            {
                "DBClusterIdentifier": "cluster-1",
                "DBClusterArn": "arn:aws:rds:us-east-1:123456789012:cluster:cluster-1",
            },
            {
                "DBClusterIdentifier": "cluster-2",
                "DBClusterArn": "arn:aws:rds:us-east-1:123456789012:cluster:cluster-2",
            },
        ]

        def mock_list_tags_for_resource(
            ResourceName: str, **kwargs: Any
        ) -> dict[str, Any]:
            if ResourceName == "arn:aws:rds:us-east-1:123456789012:cluster:cluster-1":
                return {
                    "TagList": [
                        {"Key": "Environment", "Value": "production"},
                        {"Key": "Team", "Value": "platform"},
                    ]
                }
            elif ResourceName == "arn:aws:rds:us-east-1:123456789012:cluster:cluster-2":
                return {
                    "TagList": [
                        {"Key": "Environment", "Value": "staging"},
                    ]
                }
            return {"TagList": []}

        action.client.list_tags_for_resource.side_effect = mock_list_tags_for_resource

        result = await action.execute(db_clusters)

        expected_result = [
            {
                "Tags": [
                    {"Key": "Environment", "Value": "production"},
                    {"Key": "Team", "Value": "platform"},
                ]
            },
            {
                "Tags": [
                    {"Key": "Environment", "Value": "staging"},
                ]
            },
        ]
        assert result == expected_result
        assert action.client.list_tags_for_resource.call_count == 2
        action.client.list_tags_for_resource.assert_any_call(
            ResourceName="arn:aws:rds:us-east-1:123456789012:cluster:cluster-1"
        )
        action.client.list_tags_for_resource.assert_any_call(
            ResourceName="arn:aws:rds:us-east-1:123456789012:cluster:cluster-2"
        )
        mock_logger.info.assert_called_once_with(
            "Successfully fetched tags for 2 DB clusters"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.rds.db_cluster.actions.logger")
    async def test_execute_with_recoverable_exception(
        self, mock_logger: MagicMock, action: ListTagsForResourceAction
    ) -> None:
        """Test that recoverable exceptions are skipped and logged as warnings."""
        db_clusters = [
            {
                "DBClusterIdentifier": "cluster-1",
                "DBClusterArn": "arn:aws:rds:us-east-1:123456789012:cluster:cluster-1",
            },
            {
                "DBClusterIdentifier": "cluster-2",
                "DBClusterArn": "arn:aws:rds:us-east-1:123456789012:cluster:cluster-2",
            },
        ]

        def mock_list_tags_for_resource(
            ResourceName: str, **kwargs: Any
        ) -> dict[str, Any]:
            if ResourceName == "arn:aws:rds:us-east-1:123456789012:cluster:cluster-1":
                return {"TagList": [{"Key": "Environment", "Value": "production"}]}
            raise ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
                "ListTagsForResource",
            )

        action.client.list_tags_for_resource.side_effect = mock_list_tags_for_resource

        result = await action.execute(db_clusters)

        assert result == [{"Tags": [{"Key": "Environment", "Value": "production"}]}]
        mock_logger.warning.assert_called_once()
        assert (
            "Skipping tags for DB cluster 'cluster-2'"
            in mock_logger.warning.call_args[0][0]
        )
        mock_logger.info.assert_called_once_with(
            "Successfully fetched tags for 1 DB clusters"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.rds.db_cluster.actions.logger")
    async def test_execute_with_non_recoverable_exception(
        self, mock_logger: MagicMock, action: ListTagsForResourceAction
    ) -> None:
        """Test that non-recoverable exceptions are raised."""
        db_clusters = [
            {
                "DBClusterIdentifier": "cluster-1",
                "DBClusterArn": "arn:aws:rds:us-east-1:123456789012:cluster:cluster-1",
            },
        ]

        action.client.list_tags_for_resource.side_effect = ClientError(
            {"Error": {"Code": "NetworkError", "Message": "Network timeout"}},
            "ListTagsForResource",
        )

        with pytest.raises(ClientError) as exc_info:
            await action.execute(db_clusters)

        assert exc_info.value.response["Error"]["Code"] == "NetworkError"
        mock_logger.error.assert_called_once()
        assert (
            "Error fetching tags for DB cluster 'cluster-1'"
            in mock_logger.error.call_args[0][0]
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.rds.db_cluster.actions.logger")
    async def test_execute_empty_tag_list(
        self, mock_logger: MagicMock, action: ListTagsForResourceAction
    ) -> None:
        """Test execution when a DB cluster has no tags."""
        db_clusters = [
            {
                "DBClusterIdentifier": "cluster-1",
                "DBClusterArn": "arn:aws:rds:us-east-1:123456789012:cluster:cluster-1",
            }
        ]

        action.client.list_tags_for_resource.return_value = {"TagList": []}

        result = await action.execute(db_clusters)

        assert result == [{"Tags": []}]
        action.client.list_tags_for_resource.assert_called_once_with(
            ResourceName="arn:aws:rds:us-east-1:123456789012:cluster:cluster-1"
        )
        mock_logger.info.assert_called_once_with(
            "Successfully fetched tags for 1 DB clusters"
        )


class TestRdsDbClusterActionsMap:

    def test_merge_includes_defaults(self) -> None:
        """Test that merge always includes default actions."""
        action_map = RdsDbClusterActionsMap()
        merged = action_map.merge([])
        names = [cls.__name__ for cls in merged]
        assert "DescribeDBClustersAction" in names

    def test_merge_excludes_options_by_default(self) -> None:
        """Test that optional actions are not included without being specified."""
        action_map = RdsDbClusterActionsMap()
        merged = action_map.merge([])
        names = [cls.__name__ for cls in merged]
        assert "ListTagsForResourceAction" not in names

    def test_merge_with_optional_action(self) -> None:
        """Test that merge includes optional actions when specified by name."""
        actions = RdsDbClusterActionsMap().merge(["ListTagsForResourceAction"])
        names = [a.__name__ for a in actions]
        assert "DescribeDBClustersAction" in names
        assert "ListTagsForResourceAction" in names
