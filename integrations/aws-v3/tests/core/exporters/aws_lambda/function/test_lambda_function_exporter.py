from typing import AsyncGenerator, Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.aws_lambda.function.exporter import LambdaFunctionExporter
from aws.core.exporters.aws_lambda.function.models import (
    SingleLambdaFunctionRequest,
    PaginatedLambdaFunctionRequest,
    LambdaFunction,
    LambdaFunctionProperties,
)


class TestLambdaFunctionExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock AioSession for testing."""
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> LambdaFunctionExporter:
        """Create a LambdaFunctionExporter instance for testing."""
        return LambdaFunctionExporter(mock_session)

    def test_service_name(self, exporter: LambdaFunctionExporter) -> None:
        """Test that the service name is correctly set."""
        assert exporter._service_name == "lambda"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        """Test that the exporter initializes correctly."""
        exporter = LambdaFunctionExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._client is None

    @pytest.mark.asyncio
    @patch("aws.core.exporters.aws_lambda.function.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.aws_lambda.function.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: LambdaFunctionExporter,
    ) -> None:
        """Test successful single resource retrieval."""
        # Setup mocks
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Mock the get_function call to return proper response
        mock_client.get_function.return_value = {
            "Configuration": {
                "FunctionName": "test-function",
                "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:test-function",
                "Runtime": "python3.9",
                "Handler": "index.handler",
                "MemorySize": 512,
                "Timeout": 30,
                "State": "Active",
                "LastModified": "2023-12-01T10:30:00.000+0000",
            }
        }

        # Inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        lambda_function = LambdaFunction(
            Properties=LambdaFunctionProperties(
                FunctionName="test-function",
                Runtime="python3.9",
                Handler="index.handler",
            )
        )
        mock_inspector.inspect.return_value = [lambda_function.dict(exclude_none=True)]

        options = SingleLambdaFunctionRequest(
            region="us-east-1",
            account_id="123456789012",
            function_name="test-function",
            include=[],
        )

        result = await exporter.get_resource(options)

        assert result == lambda_function.dict(exclude_none=True)
        mock_proxy_class.assert_called_once_with(
            exporter.session, "us-east-1", "lambda"
        )
        mock_inspector_class.assert_called_once()
        mock_inspector.inspect.assert_called_once()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.aws_lambda.function.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.aws_lambda.function.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: LambdaFunctionExporter,
    ) -> None:
        """Test successful retrieval of paginated Lambda functions."""
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [
                {
                    "FunctionName": "function-1",
                    "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:function-1",
                    "Runtime": "python3.9",
                    "Handler": "index.handler",
                    "MemorySize": 512,
                    "Timeout": 30,
                    "State": "Active",
                    "LastModified": "2023-12-01T10:30:00.000+0000",
                },
                {
                    "FunctionName": "function-2",
                    "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:function-2",
                    "Runtime": "nodejs18.x",
                    "Handler": "index.handler",
                    "MemorySize": 256,
                    "Timeout": 15,
                    "State": "Active",
                    "LastModified": "2023-12-01T11:00:00.000+0000",
                },
            ]
            yield [
                {
                    "FunctionName": "function-3",
                    "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:function-3",
                    "Runtime": "java11",
                    "Handler": "com.example.Handler::handleRequest",
                    "MemorySize": 1024,
                    "Timeout": 60,
                    "State": "Active",
                    "LastModified": "2023-12-01T12:00:00.000+0000",
                },
            ]

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[dict[str, Any]], None]:
                return mock_paginate()

        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        func1 = LambdaFunction(
            Properties=LambdaFunctionProperties(FunctionName="function-1")
        )
        func2 = LambdaFunction(
            Properties=LambdaFunctionProperties(FunctionName="function-2")
        )
        func3 = LambdaFunction(
            Properties=LambdaFunctionProperties(FunctionName="function-3")
        )

        mock_inspector.inspect.side_effect = [
            [func1.dict(exclude_none=True), func2.dict(exclude_none=True)],
            [func3.dict(exclude_none=True)],
        ]

        options = PaginatedLambdaFunctionRequest(
            region="us-east-1",
            account_id="123456789012",
            include=[],
        )

        collected: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            collected.extend(page)

        assert len(collected) == 3
        assert collected[0] == func1.dict(exclude_none=True)
        assert collected[1] == func2.dict(exclude_none=True)
        assert collected[2] == func3.dict(exclude_none=True)

        mock_proxy_class.assert_called_once_with(
            exporter.session, "us-east-1", "lambda"
        )
        mock_proxy.get_paginator.assert_called_once_with("list_functions", "Functions")
        assert mock_inspector.inspect.call_count == 2

    @pytest.mark.asyncio
    @patch("aws.core.exporters.aws_lambda.function.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.aws_lambda.function.exporter.ResourceInspector")
    async def test_get_paginated_resources_empty(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: LambdaFunctionExporter,
    ) -> None:
        """Test handling of empty paginated results."""
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[list[dict[str, Any]], None]:
            yield []

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[dict[str, Any]], None]:
                return mock_paginate()

        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = []

        options = PaginatedLambdaFunctionRequest(
            region="us-west-1",
            account_id="123456789012",
            include=[],
        )

        results: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        assert results == []
        mock_proxy.get_paginator.assert_called_once_with("list_functions", "Functions")
        mock_inspector.inspect.assert_not_called()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.aws_lambda.function.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.aws_lambda.function.exporter.ResourceInspector")
    async def test_context_manager_cleanup(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: LambdaFunctionExporter,
    ) -> None:
        """Test that context manager properly cleans up resources."""
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_proxy_class.return_value.__aexit__ = AsyncMock()

        # Mock the get_function call to return proper response
        mock_client.get_function.return_value = {
            "Configuration": {
                "FunctionName": "cleanup-test",
                "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:cleanup-test",
                "Runtime": "python3.9",
                "Handler": "index.handler",
                "MemorySize": 512,
                "Timeout": 30,
                "State": "Active",
                "LastModified": "2023-12-01T10:30:00.000+0000",
            }
        }

        mock_inspector = AsyncMock()
        lambda_function = LambdaFunction(
            Properties=LambdaFunctionProperties(FunctionName="cleanup-test")
        )
        mock_inspector.inspect.return_value = [lambda_function.dict(exclude_none=True)]
        mock_inspector_class.return_value = mock_inspector

        options = SingleLambdaFunctionRequest(
            region="us-west-2",
            account_id="123456789012",
            function_name="cleanup-test",
            include=[],
        )

        result = await exporter.get_resource(options)
        assert result["Properties"]["FunctionName"] == "cleanup-test"
        assert result["Type"] == "AWS::Lambda::Function"

        mock_inspector.inspect.assert_called_once()
        mock_proxy_class.assert_called_once_with(
            exporter.session, "us-west-2", "lambda"
        )
        mock_proxy_class.return_value.__aenter__.assert_called_once()
        mock_proxy_class.return_value.__aexit__.assert_called_once()
