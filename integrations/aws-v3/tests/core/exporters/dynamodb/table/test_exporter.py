from typing import AsyncGenerator, List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.dynamodb.table.exporter import DynamoDBTableExporter
from aws.core.exporters.dynamodb.table.models import (
    SingleDynamoDBTableRequest,
    PaginatedDynamoDBTableRequest,
)


class TestDynamoDBTableExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> DynamoDBTableExporter:
        return DynamoDBTableExporter(mock_session)

    def test_service_name(self, exporter: DynamoDBTableExporter) -> None:
        assert exporter._service_name == "dynamodb"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        exporter = DynamoDBTableExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._client is None

    @pytest.mark.asyncio
    @patch("aws.core.exporters.dynamodb.table.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.dynamodb.table.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: DynamoDBTableExporter,
    ) -> None:
        # Setup proxy/client
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        # Mock the inspector to return a single table
        mock_table_data = {
            "TableName": "test-table",
            "TableArn": "arn:aws:dynamodb:us-east-1:123456789012:table/test-table",
            "TableStatus": "ACTIVE",
            "ItemCount": 42,
        }
        mock_inspector.inspect.return_value = [mock_table_data]

        # Create request
        request = SingleDynamoDBTableRequest(
            table_name="test-table",
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        # Execute
        result = await exporter.get_resource(request)

        # Verify
        assert isinstance(result, dict)
        assert result["TableName"] == "test-table"
        assert (
            result["TableArn"]
            == "arn:aws:dynamodb:us-east-1:123456789012:table/test-table"
        )
        assert result["TableStatus"] == "ACTIVE"

    @pytest.mark.asyncio
    @patch("aws.core.exporters.dynamodb.table.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.dynamodb.table.exporter.ResourceInspector")
    async def test_get_resource_empty_response(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: DynamoDBTableExporter,
    ) -> None:
        # Setup proxy/client
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = []

        # Create request
        request = SingleDynamoDBTableRequest(
            table_name="non-existent-table",
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        # Execute
        result = await exporter.get_resource(request)

        # Verify empty dict is returned when inspector returns empty list
        assert result == {}

    @pytest.mark.asyncio
    @patch("aws.core.exporters.dynamodb.table.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.dynamodb.table.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: DynamoDBTableExporter,
    ) -> None:
        # Setup proxy/client
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Mock paginator
        async def mock_paginate() -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield ["table-1", "table-2"]

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
                return mock_paginate()

        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        # Inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        mock_table_data = [
            {
                "TableName": "table-1",
                "TableArn": "arn:aws:dynamodb:us-east-1:123456789012:table/table-1",
                "TableStatus": "ACTIVE",
            },
            {
                "TableName": "table-2",
                "TableArn": "arn:aws:dynamodb:us-east-1:123456789012:table/table-2",
                "TableStatus": "ACTIVE",
            },
        ]
        mock_inspector.inspect.return_value = mock_table_data

        # Create request
        request = PaginatedDynamoDBTableRequest(
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        # Execute
        results = []
        async for page in exporter.get_paginated_resources(request):
            results.extend(page)

        # Verify
        assert len(results) == 2
        assert results[0]["TableName"] == "table-1"
        assert results[1]["TableName"] == "table-2"

    @pytest.mark.asyncio
    @patch("aws.core.exporters.dynamodb.table.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.dynamodb.table.exporter.ResourceInspector")
    async def test_get_paginated_resources_empty(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: DynamoDBTableExporter,
    ) -> None:
        # Setup proxy/client
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Mock paginator to return empty list
        async def mock_paginate() -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield []

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
                return mock_paginate()

        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        # Inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = []

        # Create request
        request = PaginatedDynamoDBTableRequest(
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        # Execute
        results = []
        async for page in exporter.get_paginated_resources(request):
            results.extend(page)

        # Verify
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("aws.core.exporters.dynamodb.table.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.dynamodb.table.exporter.ResourceInspector")
    async def test_get_resource_inspector_exception(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: DynamoDBTableExporter,
    ) -> None:
        # Setup proxy/client
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Inspector raises exception
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.side_effect = Exception("Inspector error")

        # Create request
        request = SingleDynamoDBTableRequest(
            table_name="test-table",
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        # Execute and verify exception is raised
        with pytest.raises(Exception, match="Inspector error"):
            await exporter.get_resource(request)
