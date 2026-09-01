from typing import AsyncGenerator, List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.sqs.queue.exporter import SqsQueueExporter
from aws.core.exporters.sqs.queue.models import (
    SingleQueueRequest,
    PaginatedQueueRequest,
)


class TestSqsQueueExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> SqsQueueExporter:
        return SqsQueueExporter(mock_session)

    def test_service_name(self, exporter: SqsQueueExporter) -> None:
        assert exporter._service_name == "sqs"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        exporter = SqsQueueExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._client is None

    @pytest.mark.asyncio
    @patch("aws.core.exporters.sqs.queue.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.sqs.queue.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: SqsQueueExporter,
    ) -> None:
        # Setup proxy/client
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_client.get_queue_attributes.return_value = {
            "Attributes": {
                "QueueArn": "arn:aws:sqs:us-east-1:123456789012:test-queue",
            }
        }

        # Inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        # Mock the inspector to return a single queue
        mock_queue_data = {
            "QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            "Attributes": {
                "QueueArn": "arn:aws:sqs:us-east-1:123456789012:test-queue",
                "ApproximateNumberOfMessages": "5",
            },
            "Tags": {"Environment": "Production"},
        }
        mock_inspector.inspect.return_value = [mock_queue_data]

        # Create request
        request = SingleQueueRequest(
            queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            region="us-east-1",
            include=["GetQueueAttributesAction"],
            account_id="123456789012",
        )

        # Execute
        result = await exporter.get_resource(request)

        # Verify - the result should be a single dict
        assert isinstance(result, dict)
        assert (
            result["QueueUrl"]
            == "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
        )
        assert (
            result["Attributes"]["QueueArn"]
            == "arn:aws:sqs:us-east-1:123456789012:test-queue"
        )
        mock_client.get_queue_attributes.assert_awaited_once_with(
            QueueUrl="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            AttributeNames=["All"],
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.sqs.queue.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.sqs.queue.exporter.ResourceInspector")
    async def test_get_resource_queue_not_found(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: SqsQueueExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_client.get_queue_attributes.side_effect = ClientError(
            {
                "Error": {
                    "Code": "AWS.SimpleQueueService.NonExistentQueue",
                    "Message": "gone",
                }
            },
            "GetQueueAttributes",
        )

        request = SingleQueueRequest(
            queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/nonexistent",
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        with pytest.raises(ClientError) as exc_info:
            await exporter.get_resource(request)

        assert (
            exc_info.value.response["Error"]["Code"]
            == "AWS.SimpleQueueService.NonExistentQueue"
        )
        mock_inspector_class.assert_not_called()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.sqs.queue.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.sqs.queue.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: SqsQueueExporter,
    ) -> None:
        # Setup proxy/client
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Mock paginator properly
        async def mock_paginate() -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [
                {
                    "QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue-1"
                },
                {
                    "QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue-2"
                },
            ]

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
                return mock_paginate()

        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        # Inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        # Mock the inspector to return queue data
        mock_queue_data = [
            {
                "QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue-1",
                "Attributes": {
                    "QueueArn": "arn:aws:sqs:us-east-1:123456789012:test-queue-1"
                },
                "Tags": {},
            },
            {
                "QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue-2",
                "Attributes": {
                    "QueueArn": "arn:aws:sqs:us-east-1:123456789012:test-queue-2"
                },
                "Tags": {},
            },
        ]
        mock_inspector.inspect.return_value = mock_queue_data

        # Create request
        request = PaginatedQueueRequest(
            region="us-east-1",
            include=["GetQueueAttributesAction"],
            account_id="123456789012",
        )

        # Execute
        results = []
        async for page in exporter.get_paginated_resources(request):
            results.extend(page)

        # Verify
        assert len(results) == 2
        assert (
            results[0]["QueueUrl"]
            == "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue-1"
        )
        assert (
            results[1]["QueueUrl"]
            == "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue-2"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.sqs.queue.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.sqs.queue.exporter.ResourceInspector")
    async def test_get_paginated_resources_empty(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: SqsQueueExporter,
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
        request = PaginatedQueueRequest(
            region="us-east-1",
            include=["GetQueueAttributesAction"],
            account_id="123456789012",
        )

        # Execute
        results = []
        async for page in exporter.get_paginated_resources(request):
            results.extend(page)

        # Verify
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("aws.core.exporters.sqs.queue.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.sqs.queue.exporter.ResourceInspector")
    async def test_get_resource_inspector_exception(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: SqsQueueExporter,
    ) -> None:
        # Setup proxy/client
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_client.get_queue_attributes.return_value = {
            "Attributes": {
                "QueueArn": "arn:aws:sqs:us-east-1:123456789012:test-queue",
            }
        }

        # Inspector raises exception
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.side_effect = Exception("Inspector error")

        # Create request
        request = SingleQueueRequest(
            queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            region="us-east-1",
            include=["GetQueueAttributesAction"],
            account_id="123456789012",
        )

        # Execute and verify exception is raised
        with pytest.raises(Exception, match="Inspector error"):
            await exporter.get_resource(request)
