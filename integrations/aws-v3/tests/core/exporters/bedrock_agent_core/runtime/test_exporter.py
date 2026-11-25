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
    "platformVersion": "1.0",
}


class TestBedrockAgentCoreRuntimeExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(
        self, mock_session: AsyncMock
    ) -> BedrockAgentCoreRuntimeExporter:
        return BedrockAgentCoreRuntimeExporter(mock_session)

    def test_service_name(
        self, exporter: BedrockAgentCoreRuntimeExporter
    ) -> None:
        assert exporter._service_name == "bedrock-agentcore-control"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        exporter = BedrockAgentCoreRuntimeExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._client is None

    @pytest.mark.asyncio
    @patch(
        "aws.core.exporters.bedrock_agent_core.runtime.exporter.AioBaseClientProxy"
    )
    @patch(
        "aws.core.exporters.bedrock_agent_core.runtime.exporter.ResourceInspector"
    )
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
        mock_inspector.inspect.assert_awaited_once_with(
            [{"agentRuntimeId": RUNTIME_ID}],
            [],
            extra_context={"AccountId": "123456789012", "Region": "us-east-1"},
        )

    @pytest.mark.asyncio
    @patch(
        "aws.core.exporters.bedrock_agent_core.runtime.exporter.AioBaseClientProxy"
    )
    @patch(
        "aws.core.exporters.bedrock_agent_core.runtime.exporter.ResourceInspector"
    )
    async def test_get_resource_returns_empty_dict_when_not_found(
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
            agent_runtime_id="nonexistent-id",
            region="us-east-1",
            account_id="123456789012",
        )

        result = await exporter.get_resource(request)
        assert result == {}

    @pytest.mark.asyncio
    @patch(
        "aws.core.exporters.bedrock_agent_core.runtime.exporter.AioBaseClientProxy"
    )
    @patch(
        "aws.core.exporters.bedrock_agent_core.runtime.exporter.ResourceInspector"
    )
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
    @patch(
        "aws.core.exporters.bedrock_agent_core.runtime.exporter.AioBaseClientProxy"
    )
    @patch(
        "aws.core.exporters.bedrock_agent_core.runtime.exporter.ResourceInspector"
    )
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
