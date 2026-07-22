from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.elasticache.cluster.actions import (
    DescribeCacheClustersAction,
    ListTagsForResourceAction,
    ElastiCacheClusterActionsMap,
)
from aws.core.interfaces.action import Action


class TestDescribeCacheClustersAction:

    @pytest.fixture
    def action(self) -> DescribeCacheClustersAction:
        return DescribeCacheClustersAction(AsyncMock())

    def test_inheritance(self, action: DescribeCacheClustersAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_returns_input(
        self, action: DescribeCacheClustersAction
    ) -> None:
        cache_clusters = [
            {
                "CacheClusterId": "cluster-1",
                "ARN": "arn:aws:elasticache:us-east-1:123456789012:cluster:cluster-1",
            },
            {
                "CacheClusterId": "cluster-2",
                "ARN": "arn:aws:elasticache:us-east-1:123456789012:cluster:cluster-2",
            },
        ]
        result = await action.execute(cache_clusters)
        assert result == cache_clusters


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
    @patch("aws.core.exporters.elasticache.cluster.actions.logger")
    async def test_execute_success(
        self, mock_logger: MagicMock, action: ListTagsForResourceAction
    ) -> None:
        cache_clusters = [
            {
                "CacheClusterId": "cluster-1",
                "ARN": "arn:aws:elasticache:us-east-1:123456789012:cluster:cluster-1",
            },
            {
                "CacheClusterId": "cluster-2",
                "ARN": "arn:aws:elasticache:us-east-1:123456789012:cluster:cluster-2",
            },
        ]

        def mock_list_tags_for_resource(
            ResourceName: str, **kwargs: Any
        ) -> dict[str, Any]:
            if (
                ResourceName
                == "arn:aws:elasticache:us-east-1:123456789012:cluster:cluster-1"
            ):
                return {
                    "TagList": [
                        {"Key": "Environment", "Value": "production"},
                        {"Key": "Project", "Value": "web-app"},
                    ]
                }
            elif (
                ResourceName
                == "arn:aws:elasticache:us-east-1:123456789012:cluster:cluster-2"
            ):
                return {
                    "TagList": [
                        {"Key": "Environment", "Value": "staging"},
                        {"Key": "Owner", "Value": "devops-team"},
                    ]
                }
            else:
                return {"TagList": []}

        action.client.list_tags_for_resource.side_effect = mock_list_tags_for_resource

        result = await action.execute(cache_clusters)

        expected_result = [
            {
                "TagList": [
                    {"Key": "Environment", "Value": "production"},
                    {"Key": "Project", "Value": "web-app"},
                ]
            },
            {
                "TagList": [
                    {"Key": "Environment", "Value": "staging"},
                    {"Key": "Owner", "Value": "devops-team"},
                ]
            },
        ]
        assert result == expected_result

        assert action.client.list_tags_for_resource.call_count == 2
        action.client.list_tags_for_resource.assert_any_call(
            ResourceName="arn:aws:elasticache:us-east-1:123456789012:cluster:cluster-1"
        )
        action.client.list_tags_for_resource.assert_any_call(
            ResourceName="arn:aws:elasticache:us-east-1:123456789012:cluster:cluster-2"
        )

        mock_logger.info.assert_called_once_with(
            "Successfully fetched tags for 2 cache clusters"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.elasticache.cluster.actions.logger")
    async def test_execute_with_recoverable_exception(
        self, mock_logger: MagicMock, action: ListTagsForResourceAction
    ) -> None:
        cache_clusters = [
            {
                "CacheClusterId": "cluster-1",
                "ARN": "arn:aws:elasticache:us-east-1:123456789012:cluster:cluster-1",
            },
            {
                "CacheClusterId": "cluster-2",
                "ARN": "arn:aws:elasticache:us-east-1:123456789012:cluster:cluster-2",
            },
        ]

        def mock_list_tags_for_resource(
            ResourceName: str, **kwargs: Any
        ) -> dict[str, Any]:
            if (
                ResourceName
                == "arn:aws:elasticache:us-east-1:123456789012:cluster:cluster-1"
            ):
                return {"TagList": [{"Key": "Environment", "Value": "production"}]}
            else:
                raise ClientError(
                    {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
                    "ListTagsForResource",
                )

        action.client.list_tags_for_resource.side_effect = mock_list_tags_for_resource

        result = await action.execute(cache_clusters)

        expected_result = [
            {"TagList": [{"Key": "Environment", "Value": "production"}]},
            {},
        ]
        assert result == expected_result
        assert len(result) == 2

        mock_logger.warning.assert_called_once()
        warning_call = mock_logger.warning.call_args[0][0]
        assert "Skipping tags for cache cluster 'cluster-2'" in warning_call
        assert "Access denied" in warning_call

        mock_logger.info.assert_called_once_with(
            "Successfully fetched tags for 1 cache clusters"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.elasticache.cluster.actions.logger")
    async def test_execute_first_cluster_fails_maintains_index_alignment(
        self, mock_logger: MagicMock, action: ListTagsForResourceAction
    ) -> None:
        """Test that when first cluster fails, tags are correctly aligned to second cluster."""
        cache_clusters = [
            {
                "CacheClusterId": "cluster-1",
                "ARN": "arn:aws:elasticache:us-east-1:123456789012:cluster:cluster-1",
            },
            {
                "CacheClusterId": "cluster-2",
                "ARN": "arn:aws:elasticache:us-east-1:123456789012:cluster:cluster-2",
            },
        ]

        def mock_list_tags_for_resource(
            ResourceName: str, **kwargs: Any
        ) -> dict[str, Any]:
            if (
                ResourceName
                == "arn:aws:elasticache:us-east-1:123456789012:cluster:cluster-1"
            ):
                raise ClientError(
                    {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
                    "ListTagsForResource",
                )
            else:
                return {"TagList": [{"Key": "Environment", "Value": "staging"}]}

        action.client.list_tags_for_resource.side_effect = mock_list_tags_for_resource

        result = await action.execute(cache_clusters)

        expected_result = [
            {},
            {"TagList": [{"Key": "Environment", "Value": "staging"}]},
        ]
        assert result == expected_result
        assert len(result) == 2
        assert result[0] == {}
        assert result[1] == {"TagList": [{"Key": "Environment", "Value": "staging"}]}

        mock_logger.warning.assert_called_once()
        warning_call = mock_logger.warning.call_args[0][0]
        assert "Skipping tags for cache cluster 'cluster-1'" in warning_call

    @pytest.mark.asyncio
    @patch("aws.core.exporters.elasticache.cluster.actions.logger")
    async def test_execute_with_non_recoverable_exception(
        self, mock_logger: MagicMock, action: ListTagsForResourceAction
    ) -> None:
        cache_clusters = [
            {
                "CacheClusterId": "cluster-1",
                "ARN": "arn:aws:elasticache:us-east-1:123456789012:cluster:cluster-1",
            },
        ]

        def mock_list_tags_for_resource(
            ResourceName: str, **kwargs: Any
        ) -> dict[str, Any]:
            raise ClientError(
                {"Error": {"Code": "NetworkError", "Message": "Network timeout"}},
                "ListTagsForResource",
            )

        action.client.list_tags_for_resource.side_effect = mock_list_tags_for_resource

        with pytest.raises(ClientError) as exc_info:
            await action.execute(cache_clusters)

        assert exc_info.value.response["Error"]["Code"] == "NetworkError"

        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "Error fetching tags for cache cluster 'cluster-1'" in error_call
        assert "Network timeout" in error_call

    @pytest.mark.asyncio
    @patch("aws.core.exporters.elasticache.cluster.actions.logger")
    async def test_execute_empty_tag_list(
        self, mock_logger: MagicMock, action: ListTagsForResourceAction
    ) -> None:
        cache_clusters = [
            {
                "CacheClusterId": "cluster-1",
                "ARN": "arn:aws:elasticache:us-east-1:123456789012:cluster:cluster-1",
            }
        ]

        action.client.list_tags_for_resource.return_value = {"TagList": []}

        result = await action.execute(cache_clusters)

        expected_result: list[dict[str, Any]] = [{"TagList": []}]
        assert result == expected_result

        action.client.list_tags_for_resource.assert_called_once_with(
            ResourceName="arn:aws:elasticache:us-east-1:123456789012:cluster:cluster-1"
        )

        mock_logger.info.assert_called_once_with(
            "Successfully fetched tags for 1 cache clusters"
        )


class TestElastiCacheClusterActionsMap:

    def test_merge_includes_defaults(self) -> None:
        action_map = ElastiCacheClusterActionsMap()
        merged = action_map.merge([])

        names = [cls.__name__ for cls in merged]
        assert "DescribeCacheClustersAction" in names

    def test_merge_with_options(self) -> None:
        include = ["ListTagsForResourceAction"]
        actions = ElastiCacheClusterActionsMap().merge(include)
        names = [a.__name__ for a in actions]
        assert "DescribeCacheClustersAction" in names
        assert "ListTagsForResourceAction" in names

    def test_merge_with_list_tags_action(self) -> None:
        action_map = ElastiCacheClusterActionsMap()
        merged = action_map.merge(["ListTagsForResourceAction"])

        names = [cls.__name__ for cls in merged]
        assert "DescribeCacheClustersAction" in names
        assert "ListTagsForResourceAction" in names
