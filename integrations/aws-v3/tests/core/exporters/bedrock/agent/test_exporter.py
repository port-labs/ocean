from typing import AsyncGenerator, List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.bedrock.agent.exporter import BedrockAgentExporter
from aws.core.exporters.bedrock.agent.models import (
    SingleBedrockAgentRequest,
    PaginatedBedrockAgentRequest,
)


class TestBedrockAgentExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> BedrockAgentExporter:
        return BedrockAgentExporter(mock_session)

    def test_service_name(self, exporter: BedrockAgentExporter) -> None:
        assert exporter._service_name == "bedrock-agent"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        exporter = BedrockAgentExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._client is None

    @pytest.mark.asyncio
    @patch("aws.core.exporters.bedrock.agent.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.bedrock.agent.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: BedrockAgentExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_client.get_agent.return_value = {
            "agent": {
                "agentId": "ABCDEF1234",
                "agentName": "my-customer-support-agent",
                "agentArn": "arn:aws:bedrock:us-east-1:123456789012:agent/ABCDEF1234",
                "agentStatus": "PREPARED",
            }
        }

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        mock_agent_data = {
            "agentId": "ABCDEF1234",
            "agentName": "my-customer-support-agent",
            "agentArn": "arn:aws:bedrock:us-east-1:123456789012:agent/ABCDEF1234",
            "agentStatus": "PREPARED",
        }
        mock_inspector.inspect.return_value = [mock_agent_data]

        request = SingleBedrockAgentRequest(
            agent_id="ABCDEF1234",
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        result = await exporter.get_resource(request)

        assert isinstance(result, dict)
        assert result["agentId"] == "ABCDEF1234"
        assert result["agentStatus"] == "PREPARED"
        mock_client.get_agent.assert_awaited_once_with(agentId="ABCDEF1234")

    @pytest.mark.asyncio
    @patch("aws.core.exporters.bedrock.agent.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.bedrock.agent.exporter.ResourceInspector")
    async def test_get_resource_agent_not_found(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: BedrockAgentExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_client.get_agent.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Agent not found"}},
            "GetAgent",
        )

        request = SingleBedrockAgentRequest(
            agent_id="NONEXISTENT",
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        with pytest.raises(ClientError) as exc_info:
            await exporter.get_resource(request)

        assert exc_info.value.response["Error"]["Code"] == "ResourceNotFoundException"
        mock_inspector_class.assert_not_called()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.bedrock.agent.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.bedrock.agent.exporter.ResourceInspector")
    async def test_get_resource_empty(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: BedrockAgentExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_client.get_agent.return_value = {
            "agent": {
                "agentId": "ABCDEF1234",
                "agentArn": "arn:aws:bedrock:us-east-1:123456789012:agent/ABCDEF1234",
            }
        }

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = []

        request = SingleBedrockAgentRequest(
            agent_id="ABCDEF1234",
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        result = await exporter.get_resource(request)

        assert result == {}

    @pytest.mark.asyncio
    @patch("aws.core.exporters.bedrock.agent.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.bedrock.agent.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: BedrockAgentExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_proxy.client = AsyncMock()
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [
                {"agentId": "ABCDEF1234", "agentName": "agent-1", "agentStatus": "PREPARED"},
                {"agentId": "GHIJKL5678", "agentName": "agent-2", "agentStatus": "NOT_PREPARED"},
            ]

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
                return mock_paginate()

        mock_proxy.get_paginator = MagicMock(return_value=MockPaginator())

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        mock_agent_data = [
            {"agentId": "ABCDEF1234", "agentName": "agent-1"},
            {"agentId": "GHIJKL5678", "agentName": "agent-2"},
        ]
        mock_inspector.inspect.return_value = mock_agent_data

        request = PaginatedBedrockAgentRequest(
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        results = []
        async for page in exporter.get_paginated_resources(request):
            results.extend(page)

        assert len(results) == 2
        assert results[0]["agentId"] == "ABCDEF1234"
        assert results[1]["agentId"] == "GHIJKL5678"

        mock_proxy.get_paginator.assert_called_once_with("list_agents", "agentSummaries")

    @pytest.mark.asyncio
    @patch("aws.core.exporters.bedrock.agent.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.bedrock.agent.exporter.ResourceInspector")
    async def test_get_paginated_resources_empty(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: BedrockAgentExporter,
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

        request = PaginatedBedrockAgentRequest(
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        results = []
        async for page in exporter.get_paginated_resources(request):
            results.extend(page)

        assert len(results) == 0
