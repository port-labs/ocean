from typing import AsyncGenerator, List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.sns.topic.exporter import SNSTopicExporter
from aws.core.exporters.sns.topic.models import (
    SingleTopicRequest,
    PaginatedTopicRequest,
)


class TestSNSTopicExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> SNSTopicExporter:
        return SNSTopicExporter(mock_session)

    def test_service_name(self, exporter: SNSTopicExporter) -> None:
        assert exporter._service_name == "sns"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        exporter = SNSTopicExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._client is None

    @pytest.mark.asyncio
    @patch("aws.core.exporters.sns.topic.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.sns.topic.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: SNSTopicExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_client.get_topic_attributes.return_value = {
            "Attributes": {
                "TopicArn": "arn:aws:sns:us-east-1:123456789012:my-topic",
                "Owner": "123456789012",
            }
        }

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        mock_topic_data = {
            "TopicArn": "arn:aws:sns:us-east-1:123456789012:my-topic",
            "Owner": "123456789012",
            "SubscriptionsConfirmed": "3",
        }
        mock_inspector.inspect.return_value = [mock_topic_data]

        request = SingleTopicRequest(
            topic_arn="arn:aws:sns:us-east-1:123456789012:my-topic",
            region="us-east-1",
            include=["GetTopicAttributesAction"],
            account_id="123456789012",
        )

        result = await exporter.get_resource(request)

        assert isinstance(result, dict)
        assert result["TopicArn"] == "arn:aws:sns:us-east-1:123456789012:my-topic"
        mock_client.get_topic_attributes.assert_awaited_once_with(
            TopicArn="arn:aws:sns:us-east-1:123456789012:my-topic"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.sns.topic.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.sns.topic.exporter.ResourceInspector")
    async def test_get_resource_topic_not_found(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: SNSTopicExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_client.get_topic_attributes.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFound", "Message": "gone"}},
            "GetTopicAttributes",
        )

        request = SingleTopicRequest(
            topic_arn="arn:aws:sns:us-east-1:123456789012:nonexistent",
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        with pytest.raises(ClientError) as exc_info:
            await exporter.get_resource(request)

        assert exc_info.value.response["Error"]["Code"] == "ResourceNotFound"
        mock_inspector_class.assert_not_called()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.sns.topic.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.sns.topic.exporter.ResourceInspector")
    async def test_get_resource_empty(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: SNSTopicExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_client.get_topic_attributes.return_value = {
            "Attributes": {
                "TopicArn": "arn:aws:sns:us-east-1:123456789012:nonexistent",
            }
        }

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = []

        request = SingleTopicRequest(
            topic_arn="arn:aws:sns:us-east-1:123456789012:nonexistent",
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        result = await exporter.get_resource(request)

        assert result == {}

    @pytest.mark.asyncio
    @patch("aws.core.exporters.sns.topic.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.sns.topic.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: SNSTopicExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_proxy.client = AsyncMock()
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [
                {"TopicArn": "arn:aws:sns:us-east-1:123456789012:topic-1"},
                {"TopicArn": "arn:aws:sns:us-east-1:123456789012:topic-2.fifo"},
            ]

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
                return mock_paginate()

        mock_proxy.get_paginator = MagicMock(return_value=MockPaginator())

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        mock_topic_data = [
            {
                "TopicArn": "arn:aws:sns:us-east-1:123456789012:topic-1",
                "Owner": "123456789012",
            },
            {
                "TopicArn": "arn:aws:sns:us-east-1:123456789012:topic-2.fifo",
                "Owner": "123456789012",
            },
        ]
        mock_inspector.inspect.return_value = mock_topic_data

        request = PaginatedTopicRequest(
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        results = []
        async for page in exporter.get_paginated_resources(request):
            results.extend(page)

        assert len(results) == 2
        assert results[0]["TopicArn"] == "arn:aws:sns:us-east-1:123456789012:topic-1"
        assert (
            results[1]["TopicArn"] == "arn:aws:sns:us-east-1:123456789012:topic-2.fifo"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.sns.topic.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.sns.topic.exporter.ResourceInspector")
    async def test_get_paginated_resources_empty(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: SNSTopicExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_proxy.client = AsyncMock()
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield []

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
                return mock_paginate()

        mock_proxy.get_paginator = MagicMock(return_value=MockPaginator())

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        request = PaginatedTopicRequest(
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        results = []
        async for page in exporter.get_paginated_resources(request):
            results.extend(page)

        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("aws.core.exporters.sns.topic.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.sns.topic.exporter.ResourceInspector")
    async def test_get_resource_inspector_exception(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: SNSTopicExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_proxy.client = AsyncMock()
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_proxy.client.get_topic_attributes.return_value = {
            "Attributes": {
                "TopicArn": "arn:aws:sns:us-east-1:123456789012:my-topic",
            }
        }

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.side_effect = Exception("Inspector error")

        request = SingleTopicRequest(
            topic_arn="arn:aws:sns:us-east-1:123456789012:my-topic",
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        with pytest.raises(Exception, match="Inspector error"):
            await exporter.get_resource(request)
