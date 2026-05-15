"""Tests for EC2InstanceExporter.get_resource (single-instance path)."""

from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aws.core.exporters.ec2.instance.exporter import EC2InstanceExporter
from aws.core.exporters.ec2.instance.models import (
    EC2Instance,
    EC2InstanceProperties,
    SingleEC2InstanceRequest,
)


class TestEc2InstanceExporterGetResource:
    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> EC2InstanceExporter:
        return EC2InstanceExporter(mock_session)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ec2.instance.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ec2.instance.exporter.ResourceInspector")
    async def test_get_resource_passes_instance_dicts_not_raw_ids(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EC2InstanceExporter,
    ) -> None:
        """Regression: inspector must receive DescribeInstances `Instances[]`
        dicts. Passing `["i-xxx"]` strings made DescribeInstancesAction echo
        strings and caused `dict |= literal` in ResourceInspector."""
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        instance_dict: Dict[str, Any] = {
            "InstanceId": "i-0abc",
            "State": {"Name": "stopped"},
        }
        mock_client.describe_instances.return_value = {
            "Reservations": [{"Instances": [instance_dict]}]
        }

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        built = EC2Instance(
            Properties=EC2InstanceProperties(
                InstanceId="i-0abc",
                InstanceState={"Name": "stopped"},
            )
        )
        mock_inspector.inspect.return_value = [built.dict(exclude_none=True)]

        options = SingleEC2InstanceRequest(
            region="us-east-1",
            account_id="313110632971",
            instance_id="i-0abc",
            include=["DescribeInstanceStatusAction"],
        )

        result = await exporter.get_resource(options)

        assert result == built.dict(exclude_none=True)
        mock_client.describe_instances.assert_called_once_with(InstanceIds=["i-0abc"])

        call_args = mock_inspector.inspect.call_args
        instances_arg: List[Dict[str, Any]] = call_args[0][0]
        assert instances_arg == [instance_dict]
        assert call_args[1]["extra_context"] == {
            "AccountId": "313110632971",
            "Region": "us-east-1",
        }
        assert call_args[0][1] == ["DescribeInstanceStatusAction"]

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ec2.instance.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ec2.instance.exporter.ResourceInspector")
    async def test_get_resource_empty_describe_returns_empty_dict(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EC2InstanceExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_client.describe_instances.return_value = {"Reservations": []}

        options = SingleEC2InstanceRequest(
            region="us-east-1",
            account_id="313110632971",
            instance_id="i-missing",
        )

        result = await exporter.get_resource(options)
        assert result == {}
        mock_inspector_class.return_value.inspect.assert_not_called()
