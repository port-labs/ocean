from typing import AsyncGenerator, Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.elasticloadbalancingv2.load_balancer.exporter import (
    ElasticLoadBalancingV2Exporter,
)
from aws.core.exporters.elasticloadbalancingv2.load_balancer.models import (
    SingleLoadBalancerRequest,
    PaginatedLoadBalancerRequest,
    LoadBalancer,
    LoadBalancerProperties,
)


class TestElasticLoadBalancingV2Exporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> ElasticLoadBalancingV2Exporter:
        return ElasticLoadBalancingV2Exporter(mock_session)

    def test_service_name(self, exporter: ElasticLoadBalancingV2Exporter) -> None:
        assert exporter._service_name == "elasticloadbalancing"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        exporter = ElasticLoadBalancingV2Exporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._client is None

    @pytest.mark.asyncio
    @patch(
        "aws.core.exporters.elasticloadbalancingv2.load_balancer.exporter.AioBaseClientProxy"
    )
    @patch(
        "aws.core.exporters.elasticloadbalancingv2.load_balancer.exporter.ResourceInspector"
    )
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: ElasticLoadBalancingV2Exporter,
    ) -> None:
        arn = "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/my-lb/1234567890abcdef"

        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_client.describe_load_balancers.return_value = {
            "LoadBalancers": [
                {
                    "LoadBalancerArn": arn,
                    "LoadBalancerName": "my-lb",
                    "Type": "application",
                    "Scheme": "internet-facing",
                }
            ]
        }

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        lb = LoadBalancer(
            Properties=LoadBalancerProperties(
                LoadBalancerArn=arn,
                LoadBalancerName="my-lb",
                Type="application",
            )
        )
        mock_inspector.inspect.return_value = [lb.dict(exclude_none=True)]

        options = SingleLoadBalancerRequest(
            region="us-east-1",
            account_id="123456789012",
            load_balancer_arn=arn,
            include=["DescribeTagsAction"],
        )

        result = await exporter.get_resource(options)

        assert result == lb.dict(exclude_none=True)
        mock_proxy_class.assert_called_once_with(
            exporter.session, "us-east-1", "elasticloadbalancing"
        )
        mock_inspector_class.assert_called_once()
        mock_inspector.inspect.assert_called_once()

        call_args = mock_inspector.inspect.call_args
        assert call_args[0][1] == ["DescribeTagsAction"]
        assert call_args[1]["extra_context"]["AccountId"] == "123456789012"
        assert call_args[1]["extra_context"]["Region"] == "us-east-1"

    @pytest.mark.asyncio
    @patch(
        "aws.core.exporters.elasticloadbalancingv2.load_balancer.exporter.AioBaseClientProxy"
    )
    @patch(
        "aws.core.exporters.elasticloadbalancingv2.load_balancer.exporter.ResourceInspector"
    )
    async def test_get_resource_not_found(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: ElasticLoadBalancingV2Exporter,
    ) -> None:
        arn = "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/nonexistent/1234567890abcdef"

        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_client.describe_load_balancers.return_value = {"LoadBalancers": []}

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = []

        options = SingleLoadBalancerRequest(
            region="us-east-1",
            account_id="123456789012",
            load_balancer_arn=arn,
            include=[],
        )

        result = await exporter.get_resource(options)
        assert result == {}

    @pytest.mark.asyncio
    @patch(
        "aws.core.exporters.elasticloadbalancingv2.load_balancer.exporter.AioBaseClientProxy"
    )
    @patch(
        "aws.core.exporters.elasticloadbalancingv2.load_balancer.exporter.ResourceInspector"
    )
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: ElasticLoadBalancingV2Exporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [
                {
                    "LoadBalancerArn": "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/lb-1/aaa",
                    "LoadBalancerName": "lb-1",
                    "Type": "application",
                },
                {
                    "LoadBalancerArn": "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/lb-2/bbb",
                    "LoadBalancerName": "lb-2",
                    "Type": "network",
                },
            ]
            yield [
                {
                    "LoadBalancerArn": "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/lb-3/ccc",
                    "LoadBalancerName": "lb-3",
                    "Type": "application",
                },
            ]

        class MockPaginator:
            def paginate(
                self, **kwargs: Any
            ) -> AsyncGenerator[list[dict[str, Any]], None]:
                return mock_paginate()

        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        lb1 = LoadBalancer(Properties=LoadBalancerProperties(LoadBalancerName="lb-1"))
        lb2 = LoadBalancer(Properties=LoadBalancerProperties(LoadBalancerName="lb-2"))
        lb3 = LoadBalancer(Properties=LoadBalancerProperties(LoadBalancerName="lb-3"))

        mock_inspector.inspect.side_effect = [
            [lb1.dict(exclude_none=True), lb2.dict(exclude_none=True)],
            [lb3.dict(exclude_none=True)],
        ]

        options = PaginatedLoadBalancerRequest(
            region="us-east-1",
            account_id="123456789012",
            include=["DescribeTagsAction"],
        )

        collected: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            collected.extend(page)

        assert len(collected) == 3
        assert collected[0] == lb1.dict(exclude_none=True)
        assert collected[1] == lb2.dict(exclude_none=True)
        assert collected[2] == lb3.dict(exclude_none=True)

        mock_proxy_class.assert_called_once_with(
            exporter.session, "us-east-1", "elasticloadbalancing"
        )
        mock_proxy.get_paginator.assert_called_once_with(
            "describe_load_balancers", "LoadBalancers"
        )
        assert mock_inspector.inspect.call_count == 2

        calls = mock_inspector.inspect.call_args_list
        for call in calls:
            call_args = call[0]
            call_kwargs = call[1]
            assert call_args[1] == ["DescribeTagsAction"]
            assert call_kwargs["extra_context"]["AccountId"] == "123456789012"
            assert call_kwargs["extra_context"]["Region"] == "us-east-1"

    @pytest.mark.asyncio
    @patch(
        "aws.core.exporters.elasticloadbalancingv2.load_balancer.exporter.AioBaseClientProxy"
    )
    @patch(
        "aws.core.exporters.elasticloadbalancingv2.load_balancer.exporter.ResourceInspector"
    )
    async def test_get_paginated_resources_empty(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: ElasticLoadBalancingV2Exporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[list[dict[str, Any]], None]:
            yield []

        class MockPaginator:
            def paginate(
                self, **kwargs: Any
            ) -> AsyncGenerator[list[dict[str, Any]], None]:
                return mock_paginate()

        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        options = PaginatedLoadBalancerRequest(
            region="eu-west-1",
            account_id="123456789012",
            include=[],
        )

        results: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        assert results == []
        mock_proxy.get_paginator.assert_called_once_with(
            "describe_load_balancers", "LoadBalancers"
        )
        mock_inspector.inspect.assert_not_called()

    @pytest.mark.asyncio
    @patch(
        "aws.core.exporters.elasticloadbalancingv2.load_balancer.exporter.AioBaseClientProxy"
    )
    @patch(
        "aws.core.exporters.elasticloadbalancingv2.load_balancer.exporter.ResourceInspector"
    )
    async def test_context_manager_cleanup(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: ElasticLoadBalancingV2Exporter,
    ) -> None:
        arn = "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/my-lb/1234567890abcdef"

        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_proxy_class.return_value.__aexit__ = AsyncMock()

        mock_client.describe_load_balancers.return_value = {
            "LoadBalancers": [
                {"LoadBalancerArn": arn, "LoadBalancerName": "my-lb"}
            ]
        }

        mock_inspector = AsyncMock()
        lb = LoadBalancer(
            Properties=LoadBalancerProperties(
                LoadBalancerArn=arn, LoadBalancerName="my-lb"
            )
        )
        mock_inspector.inspect.return_value = [lb.dict(exclude_none=True)]
        mock_inspector_class.return_value = mock_inspector

        options = SingleLoadBalancerRequest(
            region="us-east-1",
            account_id="123456789012",
            load_balancer_arn=arn,
            include=[],
        )

        result = await exporter.get_resource(options)
        assert result["Properties"]["LoadBalancerName"] == "my-lb"
        assert result["Type"] == "AWS::ElasticLoadBalancingV2::LoadBalancer"

        mock_proxy_class.return_value.__aenter__.assert_called_once()
        mock_proxy_class.return_value.__aexit__.assert_called_once()
