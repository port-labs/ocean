from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.dynamodb.table.exporter import DynamoDBTableExporter
from aws.core.exporters.dynamodb.table.models import (
    SingleTableRequest,
    Table,
    TableProperties,
)


class TestDynamoDBTableExporter:
    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> DynamoDBTableExporter:
        return DynamoDBTableExporter(mock_session)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.dynamodb.table.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.dynamodb.table.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: DynamoDBTableExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        expected_table = Table(
            Properties=TableProperties(
                TableName="my-table",
                TableArn="arn:aws:dynamodb:us-east-1:123456789012:table/my-table",
            ),
        )
        mock_inspector.inspect.return_value = [
            expected_table.model_dump(exclude_none=True)
        ]

        options = SingleTableRequest(
            region="us-east-1",
            account_id="123456789012",
            table_name="my-table",
            include=[],
        )

        result = await exporter.get_resource(options)

        assert result == expected_table.model_dump(exclude_none=True)
        mock_client.describe_table.assert_awaited_once_with(TableName="my-table")
        mock_inspector.inspect.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.dynamodb.table.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.dynamodb.table.exporter.ResourceInspector")
    async def test_get_resource_describe_table_not_found(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: DynamoDBTableExporter,
    ) -> None:
        """Missing tables must raise from describe_table before stub resources are built."""
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_client.describe_table.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
            "DescribeTable",
        )

        options = SingleTableRequest(
            region="us-east-1",
            account_id="123456789012",
            table_name="nonexistent-table",
            include=[],
        )

        with pytest.raises(ClientError) as exc_info:
            await exporter.get_resource(options)

        assert exc_info.value.response["Error"]["Code"] == "ResourceNotFoundException"
        mock_inspector_class.assert_not_called()
