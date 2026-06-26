from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.elasticloadbalancingv2.load_balancer.actions import (
    DescribeLoadBalancersAction,
    DescribeTagsAction,
    ElasticLoadBalancingV2ActionsMap,
)
from aws.core.interfaces.action import Action


class TestDescribeLoadBalancersAction:

    @pytest.fixture
    def action(self) -> DescribeLoadBalancersAction:
        return DescribeLoadBalancersAction(AsyncMock())

    def test_inheritance(self, action: DescribeLoadBalancersAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_returns_input(
        self, action: DescribeLoadBalancersAction
    ) -> None:
        load_balancers = [
            {
                "LoadBalancerArn": "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/my-lb/1234567890abcdef",
                "LoadBalancerName": "my-lb",
            },
            {
                "LoadBalancerArn": "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/my-lb-2/abcdef1234567890",
                "LoadBalancerName": "my-lb-2",
            },
        ]
        result = await action.execute(load_balancers)
        assert result == load_balancers

    @pytest.mark.asyncio
    async def test_execute_empty(self, action: DescribeLoadBalancersAction) -> None:
        result = await action.execute([])
        assert result == []


class TestDescribeTagsAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        client = AsyncMock()
        client.describe_tags = AsyncMock()
        return client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> DescribeTagsAction:
        return DescribeTagsAction(mock_client)

    def test_inheritance(self, action: DescribeTagsAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.elasticloadbalancingv2.load_balancer.actions.logger")
    async def test_execute_success(
        self, mock_logger: MagicMock, action: DescribeTagsAction
    ) -> None:
        arn1 = "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/my-lb/1234567890abcdef"
        arn2 = "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/my-lb-2/abcdef1234567890"
        load_balancers = [
            {"LoadBalancerArn": arn1, "LoadBalancerName": "my-lb"},
            {"LoadBalancerArn": arn2, "LoadBalancerName": "my-lb-2"},
        ]

        action.client.describe_tags.return_value = {
            "TagDescriptions": [
                {
                    "ResourceArn": arn1,
                    "Tags": [{"Key": "Environment", "Value": "production"}],
                },
                {
                    "ResourceArn": arn2,
                    "Tags": [{"Key": "Environment", "Value": "staging"}],
                },
            ]
        }

        result = await action.execute(load_balancers)

        assert len(result) == 2
        assert result[0] == {"Tags": [{"Key": "Environment", "Value": "production"}]}
        assert result[1] == {"Tags": [{"Key": "Environment", "Value": "staging"}]}

        action.client.describe_tags.assert_called_once_with(
            ResourceArns=[arn1, arn2]
        )
        mock_logger.info.assert_called_once_with(
            "Successfully fetched tags for 2 load balancers"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.elasticloadbalancingv2.load_balancer.actions.logger")
    async def test_execute_empty_tags(
        self, mock_logger: MagicMock, action: DescribeTagsAction
    ) -> None:
        arn = "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/my-lb/1234567890abcdef"
        load_balancers = [{"LoadBalancerArn": arn, "LoadBalancerName": "my-lb"}]

        action.client.describe_tags.return_value = {
            "TagDescriptions": [
                {"ResourceArn": arn, "Tags": []},
            ]
        }

        result = await action.execute(load_balancers)

        assert len(result) == 1
        assert result[0] == {"Tags": []}

    @pytest.mark.asyncio
    async def test_execute_empty_input(self, action: DescribeTagsAction) -> None:
        result = await action.execute([])
        assert result == []
        action.client.describe_tags.assert_not_called()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.elasticloadbalancingv2.load_balancer.actions.logger")
    async def test_execute_with_recoverable_exception(
        self, mock_logger: MagicMock, action: DescribeTagsAction
    ) -> None:
        arn = "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/my-lb/1234567890abcdef"
        load_balancers = [{"LoadBalancerArn": arn, "LoadBalancerName": "my-lb"}]

        action.client.describe_tags.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "DescribeTags",
        )

        result = await action.execute(load_balancers)

        assert len(result) == 1
        assert result[0] == {"Tags": []}
        mock_logger.warning.assert_called_once()
        warning_call = mock_logger.warning.call_args[0][0]
        assert "Skipping tags for load balancer batch" in warning_call

    @pytest.mark.asyncio
    @patch("aws.core.exporters.elasticloadbalancingv2.load_balancer.actions.logger")
    async def test_execute_with_non_recoverable_exception(
        self, mock_logger: MagicMock, action: DescribeTagsAction
    ) -> None:
        arn = "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/my-lb/1234567890abcdef"
        load_balancers = [{"LoadBalancerArn": arn, "LoadBalancerName": "my-lb"}]

        action.client.describe_tags.side_effect = ClientError(
            {"Error": {"Code": "NetworkError", "Message": "Network timeout"}},
            "DescribeTags",
        )

        with pytest.raises(ClientError) as exc_info:
            await action.execute(load_balancers)

        assert exc_info.value.response["Error"]["Code"] == "NetworkError"
        mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.elasticloadbalancingv2.load_balancer.actions.logger")
    async def test_execute_batch_calls(
        self, mock_logger: MagicMock, action: DescribeTagsAction
    ) -> None:
        """Test that more than 20 load balancers are split into multiple batch calls."""
        load_balancers = [
            {
                "LoadBalancerArn": f"arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/lb-{i}/{'a' * 16}",
                "LoadBalancerName": f"lb-{i}",
            }
            for i in range(25)
        ]

        def mock_describe_tags(ResourceArns: list[str]) -> dict[str, Any]:
            return {
                "TagDescriptions": [
                    {"ResourceArn": arn, "Tags": [{"Key": "Index", "Value": str(i)}]}
                    for i, arn in enumerate(ResourceArns)
                ]
            }

        action.client.describe_tags.side_effect = mock_describe_tags

        result = await action.execute(load_balancers)

        assert len(result) == 25
        # Should have been called twice (20 + 5)
        assert action.client.describe_tags.call_count == 2


class TestElasticLoadBalancingV2ActionsMap:

    def test_merge_includes_defaults(self) -> None:
        action_map = ElasticLoadBalancingV2ActionsMap()
        merged = action_map.merge([])
        names = [cls.__name__ for cls in merged]
        assert "DescribeLoadBalancersAction" in names

    def test_merge_with_options(self) -> None:
        include = ["DescribeTagsAction"]
        actions = ElasticLoadBalancingV2ActionsMap().merge(include)
        names = [a.__name__ for a in actions]
        assert "DescribeLoadBalancersAction" in names
        assert "DescribeTagsAction" in names

    def test_merge_defaults_only(self) -> None:
        action_map = ElasticLoadBalancingV2ActionsMap()
        merged = action_map.merge([])
        names = [cls.__name__ for cls in merged]
        assert "DescribeLoadBalancersAction" in names
        assert "DescribeTagsAction" not in names
