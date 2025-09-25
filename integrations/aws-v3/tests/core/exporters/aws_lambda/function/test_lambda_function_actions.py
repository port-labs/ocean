from typing import Any
from unittest.mock import AsyncMock
import pytest

from aws.core.exporters.aws_lambda.function.actions import (
    ListFunctionsAction,
    LambdaFunctionActionsMap,
)
from aws.core.interfaces.action import Action


class TestListFunctionsAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        mock_client = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> ListFunctionsAction:
        """Create a ListFunctionsAction instance for testing."""
        return ListFunctionsAction(mock_client)

    def test_inheritance(self, action: ListFunctionsAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: ListFunctionsAction) -> None:
        """Test successful execution of list_functions."""
        functions = [
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

        result = await action.execute(functions)

        assert result == functions
        assert len(result) == 2
        assert result[0]["FunctionName"] == "function-1"
        assert result[1]["FunctionName"] == "function-2"

    @pytest.mark.asyncio
    async def test_execute_empty_list(self, action: ListFunctionsAction) -> None:
        """Test execution with empty function list."""
        functions: list[dict[str, Any]] = []

        result = await action.execute(functions)

        assert result == []
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_execute_single_function(self, action: ListFunctionsAction) -> None:
        """Test execution with single function."""
        functions = [
            {
                "FunctionName": "single-function",
                "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:single-function",
                "Runtime": "python3.9",
                "Handler": "main.handler",
                "MemorySize": 1024,
                "Timeout": 60,
                "State": "Active",
                "LastModified": "2023-12-01T12:00:00.000+0000",
            }
        ]

        result = await action.execute(functions)

        assert result == functions
        assert len(result) == 1
        assert result[0]["FunctionName"] == "single-function"
        assert result[0]["MemorySize"] == 1024


class TestLambdaFunctionActionsMap:

    def test_merge_includes_defaults(self) -> None:
        """Test that merge includes default actions."""
        action_map = LambdaFunctionActionsMap()
        merged = action_map.merge([])

        # Default is ListFunctionsAction
        names = [cls.__name__ for cls in merged]
        assert "ListFunctionsAction" in names

    def test_merge_with_empty_options(self) -> None:
        """Test that merge works with empty options list."""
        action_map = LambdaFunctionActionsMap()
        merged = action_map.merge([])

        names = [cls.__name__ for cls in merged]
        assert "ListFunctionsAction" in names
        assert len(names) == 1

    def test_merge_with_nonexistent_options(self) -> None:
        """Test that merge handles nonexistent option actions gracefully."""
        action_map = LambdaFunctionActionsMap()
        merged = action_map.merge(["NonExistentAction"])

        # Should still include defaults
        names = [cls.__name__ for cls in merged]
        assert "ListFunctionsAction" in names
