from typing import AsyncGenerator, List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.ec2.instance.exporter import EC2InstanceExporter
from aws.core.exporters.ec2.instance.models import (
    SingleEC2InstanceRequest,
    PaginatedEC2InstanceRequest,
    EC2Instance,
    EC2InstanceProperties,
)


class TestEC2InstanceExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> EC2InstanceExporter:
        return EC2InstanceExporter(mock_session)

    def test_service_name(self, exporter: EC2InstanceExporter) -> None:
        assert exporter._service_name == "ec2"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        exporter = EC2InstanceExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._client is None

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ec2.instance.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ec2.instance.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EC2InstanceExporter,
    ) -> None:
        # Setup proxy/client
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        instance = EC2Instance(
            Properties=EC2InstanceProperties(
                InstanceId="i-1234567890abcdef0", InstanceType="t3.micro"
            )
        )
        mock_inspector.inspect.return_value = [instance.dict(exclude_none=True)]

        options = SingleEC2InstanceRequest(
            region="us-west-2",
            account_id="123456789012",
            instance_id="i-1234567890abcdef0",
            include=["GetInstanceStatusAction"],
        )

        result = await exporter.get_resource(options)

        assert result == instance.dict(exclude_none=True)
        mock_proxy_class.assert_called_once_with(exporter.session, "us-west-2", "ec2")
        mock_inspector_class.assert_called_once()
        mock_inspector.inspect.assert_called_once_with(
            ["i-1234567890abcdef0"], ["GetInstanceStatusAction"]
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ec2.instance.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ec2.instance.exporter.ResourceInspector")
    async def test_get_resource_inspector_exception(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EC2InstanceExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.side_effect = Exception("Instance not found")

        options = SingleEC2InstanceRequest(
            region="us-east-1",
            account_id="123456789012",
            instance_id="i-notexists",
            include=[],
        )

        with pytest.raises(Exception, match="Instance not found"):
            await exporter.get_resource(options)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ec2.instance.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ec2.instance.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EC2InstanceExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [
                {
                    "Instances": [
                        {"InstanceId": "i-1", "InstanceType": "t3.micro"},
                        {"InstanceId": "i-2", "InstanceType": "t3.small"},
                    ],
                    "ReservationId": "r-1",
                    "OwnerId": "123456789012",
                }
            ]
            yield [
                {
                    "Instances": [
                        {"InstanceId": "i-3", "InstanceType": "t3.medium"},
                    ],
                    "ReservationId": "r-2",
                    "OwnerId": "123456789012",
                }
            ]

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
                return mock_paginate()

        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        inst1 = EC2Instance(Properties=EC2InstanceProperties(InstanceId="i-1"))
        inst2 = EC2Instance(Properties=EC2InstanceProperties(InstanceId="i-2"))
        inst3 = EC2Instance(Properties=EC2InstanceProperties(InstanceId="i-3"))

        mock_inspector.inspect.side_effect = [
            [inst1.dict(exclude_none=True), inst2.dict(exclude_none=True)],
            [inst3.dict(exclude_none=True)],
        ]

        options = PaginatedEC2InstanceRequest(
            region="us-east-1",
            account_id="123456789012",
            include=["GetInstanceStatusAction"],
        )

        collected: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            collected.extend(page)

        assert len(collected) == 3
        assert collected[0] == inst1.dict(exclude_none=True)
        assert collected[1] == inst2.dict(exclude_none=True)
        assert collected[2] == inst3.dict(exclude_none=True)

        mock_proxy_class.assert_called_once_with(exporter.session, "us-east-1", "ec2")
        mock_proxy.get_paginator.assert_called_once_with(
            "describe_instances", "Reservations"
        )
        assert mock_inspector.inspect.call_count == 2
        mock_inspector.inspect.assert_any_call(
            [
                {"InstanceId": "i-1", "InstanceType": "t3.micro"},
                {"InstanceId": "i-2", "InstanceType": "t3.small"},
            ],
            ["GetInstanceStatusAction"],
            extra_context={
                "AccountId": "123456789012",
                "Region": "us-east-1",
                "ReservationId": "r-1",
                "OwnerId": "123456789012",
            },
        )
        mock_inspector.inspect.assert_any_call(
            [
                {"InstanceId": "i-3", "InstanceType": "t3.medium"},
            ],
            ["GetInstanceStatusAction"],
            extra_context={
                "AccountId": "123456789012",
                "Region": "us-east-1",
                "ReservationId": "r-2",
                "OwnerId": "123456789012",
            },
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ec2.instance.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ec2.instance.exporter.ResourceInspector")
    async def test_get_paginated_resources_empty(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EC2InstanceExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield []

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
                return mock_paginate()

        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = []

        options = PaginatedEC2InstanceRequest(
            region="us-west-1",
            account_id="123456789012",
            include=[],
        )

        results: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        assert results == []
        mock_proxy.get_paginator.assert_called_once_with(
            "describe_instances", "Reservations"
        )
        mock_inspector.inspect.assert_not_called()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ec2.instance.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ec2.instance.exporter.ResourceInspector")
    async def test_context_manager_cleanup(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EC2InstanceExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_proxy_class.return_value.__aexit__ = AsyncMock()

        mock_inspector = AsyncMock()
        instance = EC2Instance(Properties=EC2InstanceProperties(InstanceId="i-55"))
        mock_inspector.inspect.return_value = [instance.dict(exclude_none=True)]
        mock_inspector_class.return_value = mock_inspector

        options = SingleEC2InstanceRequest(
            region="us-west-2",
            account_id="123456789012",
            instance_id="i-55",
            include=[],
        )

        result = await exporter.get_resource(options)
        assert result["Properties"]["InstanceId"] == "i-55"
        assert result["Type"] == "AWS::EC2::Instance"

        mock_inspector.inspect.assert_called_once_with(["i-55"], [])
        mock_proxy_class.assert_called_once_with(exporter.session, "us-west-2", "ec2")
        mock_proxy_class.return_value.__aenter__.assert_called_once()
        mock_proxy_class.return_value.__aexit__.assert_called_once()
