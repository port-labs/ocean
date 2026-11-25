from datetime import datetime, timezone
from typing import AsyncGenerator, List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aws.core.exporters.bedrock_agent_core.runtime.exporter import (
    BedrockAgentCoreRuntimeExporter,
)
from aws.core.exporters.bedrock_agent_core.runtime.models import (
    PaginatedBedrockAgentCoreRuntimeRequest,
    SingleBedrockAgentCoreRuntimeRequest,
)

RUNTIME_ID = "my-runtime-Ab1Cd2Ef3G"
RUNTIME_ARN = f"arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/{RUNTIME_ID}"

SAMPLE_RUNTIME: dict[str, Any] = {
    "agentRuntimeId": RUNTIME_ID,
    "agentRuntimeArn": RUNTIME_ARN,
    "agentRuntimeName": "my-runtime",
    "agentRuntimeVersion": "1",
    "status": "READY",
    "description": "Test runtime",
    "lastUpdatedAt": "2025-06-01T12:00:00Z",
    "createdAt": "2025-05-15T09:30:00Z",
    "roleArn": "arn:aws:iam::123456789012:role/MyRole",
    "networkConfiguration": {"networkMode": "PUBLIC"},
}


class TestBedrockAgentCoreRuntimeExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> BedrockAgentCoreRuntimeExporter:
        return BedrockAgentCoreRuntimeExporter(mock_session)

    def test_service_name(self, exporter: BedrockAgentCoreRuntimeExporter) -> None:
        assert exporter._service_name == "bedrock-agentcore-control"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        exporter = BedrockAgentCoreRuntimeExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._client is None

    @pytest.mark.asyncio
    @patch("aws.core.exporters.bedrock_agent_core.runtime.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.bedrock_agent_core.runtime.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: BedrockAgentCoreRuntimeExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = [SAMPLE_RUNTIME]

        request = SingleBedrockAgentCoreRuntimeRequest(
            agent_runtime_id=RUNTIME_ID,
            region="us-east-1",
            account_id="123456789012",
        )

        result = await exporter.get_resource(request)

        assert isinstance(result, dict)
        assert result["agentRuntimeId"] == RUNTIME_ID
        assert result["agentRuntimeArn"] == RUNTIME_ARN
        # No direct AWS call: the actions are seeded with only the ID and ARN.
        mock_client.get_agent_runtime.assert_not_called()
        mock_inspector.inspect.assert_awaited_once_with(
            [{"agentRuntimeId": RUNTIME_ID, "agentRuntimeArn": RUNTIME_ARN}],
            [],
            extra_context={"AccountId": "123456789012", "Region": "us-east-1"},
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.bedrock_agent_core.runtime.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.bedrock_agent_core.runtime.exporter.ResourceInspector")
    async def test_get_resource_returns_empty_dict_when_inspector_returns_nothing(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: BedrockAgentCoreRuntimeExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_proxy.client = AsyncMock()
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = []

        request = SingleBedrockAgentCoreRuntimeRequest(
            agent_runtime_id=RUNTIME_ID,
            region="us-east-1",
            account_id="123456789012",
        )

        result = await exporter.get_resource(request)
        assert result == {}

    @pytest.mark.asyncio
    @patch("aws.core.exporters.bedrock_agent_core.runtime.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.bedrock_agent_core.runtime.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: BedrockAgentCoreRuntimeExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_proxy.client = AsyncMock()
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [
                {"agentRuntimeId": "runtime-1", "agentRuntimeArn": "arn:1"},
                {"agentRuntimeId": "runtime-2", "agentRuntimeArn": "arn:2"},
            ]

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
                return mock_paginate()

        mock_proxy.get_paginator = MagicMock(return_value=MockPaginator())

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = [
            {**SAMPLE_RUNTIME, "agentRuntimeId": "runtime-1"},
            {**SAMPLE_RUNTIME, "agentRuntimeId": "runtime-2"},
        ]

        request = PaginatedBedrockAgentCoreRuntimeRequest(
            region="us-east-1",
            account_id="123456789012",
        )

        results: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(request):
            results.extend(page)

        assert len(results) == 2
        assert results[0]["agentRuntimeId"] == "runtime-1"
        assert results[1]["agentRuntimeId"] == "runtime-2"
        mock_proxy.get_paginator.assert_called_once_with(
            "list_agent_runtimes", "agentRuntimes"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.bedrock_agent_core.runtime.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.bedrock_agent_core.runtime.exporter.ResourceInspector")
    async def test_get_paginated_resources_empty(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: BedrockAgentCoreRuntimeExporter,
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
        mock_inspector.inspect.return_value = []

        request = PaginatedBedrockAgentCoreRuntimeRequest(
            region="us-east-1",
            account_id="123456789012",
        )

        results: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(request):
            results.extend(page)

        assert len(results) == 0

    def test_supported_regions(self, exporter: BedrockAgentCoreRuntimeExporter) -> None:
        assert "us-east-1" in exporter._supported_regions
        assert "us-gov-west-1" in exporter._supported_regions

    @pytest.mark.asyncio
    @patch("aws.core.exporters.bedrock_agent_core.runtime.exporter.AioBaseClientProxy")
    async def test_get_resource_end_to_end_makes_one_get_call(
        self,
        mock_proxy_class: MagicMock,
        exporter: BedrockAgentCoreRuntimeExporter,
    ) -> None:
        """Real inspector: one GetAgentRuntime call, tags fetched by the seeded ARN."""
        mock_proxy = AsyncMock()
        mock_proxy.client = AsyncMock()
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_proxy.client.get_agent_runtime.return_value = {
            **SAMPLE_RUNTIME,
            "ResponseMetadata": {"HTTPStatusCode": 200},
        }
        mock_proxy.client.list_tags_for_resource.return_value = {
            "tags": {"Team": "commerce"}
        }

        result = await exporter.get_resource(
            SingleBedrockAgentCoreRuntimeRequest(
                agent_runtime_id=RUNTIME_ID,
                region="us-east-1",
                account_id="123456789012",
                include=["ListAgentRuntimeTagsAction"],
            )
        )

        mock_proxy.client.get_agent_runtime.assert_awaited_once_with(
            agentRuntimeId=RUNTIME_ID
        )
        mock_proxy.client.list_tags_for_resource.assert_awaited_once_with(
            resourceArn=RUNTIME_ARN
        )
        assert result["Properties"]["AgentRuntimeArn"] == RUNTIME_ARN
        assert result["Properties"]["AgentRuntimeName"] == "my-runtime"
        assert result["Properties"]["Tags"] == {"Team": "commerce"}

    @pytest.mark.asyncio
    @patch("aws.core.exporters.bedrock_agent_core.runtime.exporter.AioBaseClientProxy")
    async def test_get_paginated_resources_end_to_end(
        self,
        mock_proxy_class: MagicMock,
        exporter: BedrockAgentCoreRuntimeExporter,
    ) -> None:
        """Real inspector and model, with the datetimes and secrets AWS returns."""
        mock_proxy = AsyncMock()
        mock_proxy.client = AsyncMock()
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        list_item = {
            "agentRuntimeId": RUNTIME_ID,
            "agentRuntimeArn": RUNTIME_ARN,
            "agentRuntimeName": "my-runtime",
            "status": "READY",
            "lastUpdatedAt": datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
        }

        async def mock_paginate() -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [list_item]

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
                return mock_paginate()

        mock_proxy.get_paginator = MagicMock(return_value=MockPaginator())
        mock_proxy.client.get_agent_runtime.return_value = {
            **list_item,
            "createdAt": datetime(2026, 5, 15, 9, 30, tzinfo=timezone.utc),
            "protocolConfiguration": {"serverProtocol": "MCP"},
            "environmentVariables": {"OPENAI_API_KEY": "sk-SECRET"},
            "metadataConfiguration": {"requireMMDSV2": True},
            "ResponseMetadata": {"HTTPStatusCode": 200},
        }
        mock_proxy.client.list_tags_for_resource.return_value = {
            "tags": {"Team": "commerce"}
        }

        request = PaginatedBedrockAgentCoreRuntimeRequest(
            region="us-east-1",
            account_id="123456789012",
            include=["ListAgentRuntimeTagsAction"],
        )
        results = [
            item
            async for page in exporter.get_paginated_resources(request)
            for item in page
        ]

        assert len(results) == 1
        runtime = results[0]
        assert runtime["Type"] == "AWS::BedrockAgentCore::Runtime"
        properties = runtime["Properties"]
        assert properties["AgentRuntimeArn"] == RUNTIME_ARN
        assert properties["CreatedAt"] == "2026-05-15T09:30:00Z"
        assert properties["ProtocolConfiguration"] == {"serverProtocol": "MCP"}
        assert properties["Tags"] == {"Team": "commerce"}
        assert "sk-SECRET" not in str(runtime)
        assert "EnvironmentVariables" not in properties
        assert "ResponseMetadata" not in properties
