from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.aws_lambda.function.actions import (
    ListFunctionsAction,
    ListTagsAction,
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


class TestListTagsAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock AioBaseClient for testing."""
        mock_client = AsyncMock()
        mock_client.list_tags = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> ListTagsAction:
        """Create a ListTagsAction instance for testing."""
        return ListTagsAction(mock_client)

    def test_inheritance(self, action: ListTagsAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.aws_lambda.function.actions.logger")
    async def test_execute_success(
        self, mock_logger: MagicMock, action: ListTagsAction
    ) -> None:
        """Test successful execution of list_tags."""
        functions = [
            {
                "FunctionName": "function-1",
                "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:function-1",
            },
            {
                "FunctionName": "function-2",
                "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:function-2",
            },
        ]

        # Mock should return different responses for each individual call
        def mock_list_tags(Resource: str, **kwargs: Any) -> dict[str, Any]:
            if Resource == "arn:aws:lambda:us-east-1:123456789012:function:function-1":
                return {
                    "Tags": {
                        "Environment": "production",
                        "Project": "web-app",
                    }
                }
            elif (
                Resource == "arn:aws:lambda:us-east-1:123456789012:function:function-2"
            ):
                return {
                    "Tags": {
                        "Environment": "staging",
                        "Owner": "devops-team",
                    }
                }
            else:
                return {"Tags": {}}

        action.client.list_tags.side_effect = mock_list_tags

        result = await action.execute(functions)

        expected_result = [
            {
                "Tags": {
                    "Environment": "production",
                    "Project": "web-app",
                }
            },
            {
                "Tags": {
                    "Environment": "staging",
                    "Owner": "devops-team",
                }
            },
        ]
        assert result == expected_result

        # Verify that list_tags was called twice (once for each function)
        assert action.client.list_tags.call_count == 2
        action.client.list_tags.assert_any_call(
            Resource="arn:aws:lambda:us-east-1:123456789012:function:function-1"
        )
        action.client.list_tags.assert_any_call(
            Resource="arn:aws:lambda:us-east-1:123456789012:function:function-2"
        )

        # Verify logging
        mock_logger.info.assert_called_once_with(
            "Successfully fetched tags for 2 Lambda functions"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.aws_lambda.function.actions.logger")
    async def test_execute_with_recoverable_exception(
        self, mock_logger: MagicMock, action: ListTagsAction
    ) -> None:
        """Test that recoverable exceptions are handled gracefully and logged as warnings."""
        functions = [
            {
                "FunctionName": "function-1",
                "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:function-1",
            },
            {
                "FunctionName": "function-2",
                "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:function-2",
            },
        ]

        # First call succeeds, second call fails with AccessDenied (recoverable)
        def mock_list_tags(Resource: str, **kwargs: Any) -> dict[str, Any]:
            if Resource == "arn:aws:lambda:us-east-1:123456789012:function:function-1":
                return {"Tags": {"Environment": "production"}}
            else:
                raise ClientError(
                    {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
                    "ListTags",
                )

        action.client.list_tags.side_effect = mock_list_tags

        result = await action.execute(functions)

        # Should only return results for successful calls
        expected_result = [{"Tags": {"Environment": "production"}}]
        assert result == expected_result

        # Verify warning logging for recoverable exception
        mock_logger.warning.assert_called_once()
        warning_call = mock_logger.warning.call_args[0][0]
        assert "Skipping tags for Lambda function 'function-2'" in warning_call
        assert "Access denied" in warning_call

        # Verify success logging
        mock_logger.info.assert_called_once_with(
            "Successfully fetched tags for 1 Lambda functions"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.aws_lambda.function.actions.logger")
    async def test_execute_with_non_recoverable_exception(
        self, mock_logger: MagicMock, action: ListTagsAction
    ) -> None:
        """Test that non-recoverable exceptions are raised."""
        functions = [
            {
                "FunctionName": "function-1",
                "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:function-1",
            },
        ]

        # Mock a non-recoverable exception (network error)
        def mock_list_tags(Resource: str, **kwargs: Any) -> dict[str, Any]:
            raise ClientError(
                {"Error": {"Code": "NetworkError", "Message": "Network timeout"}},
                "ListTags",
            )

        action.client.list_tags.side_effect = mock_list_tags

        # Should raise the exception
        with pytest.raises(ClientError) as exc_info:
            await action.execute(functions)

        assert exc_info.value.response["Error"]["Code"] == "NetworkError"

        # Verify error logging
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "Error fetching tags for Lambda function 'function-1'" in error_call
        assert "Network timeout" in error_call

    @pytest.mark.asyncio
    @patch("aws.core.exporters.aws_lambda.function.actions.logger")
    async def test_execute_empty_tag_list(
        self, mock_logger: MagicMock, action: ListTagsAction
    ) -> None:
        """Test execution when Lambda function has no tags."""
        functions = [
            {
                "FunctionName": "function-1",
                "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:function-1",
            }
        ]

        action.client.list_tags.return_value = {"Tags": {}}

        result = await action.execute(functions)

        expected_result: list[dict[str, Any]] = [{"Tags": {}}]
        assert result == expected_result

        action.client.list_tags.assert_called_once_with(
            Resource="arn:aws:lambda:us-east-1:123456789012:function:function-1"
        )

        mock_logger.info.assert_called_once_with(
            "Successfully fetched tags for 1 Lambda functions"
        )


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

    def test_merge_with_options(self) -> None:
        """Test that merge includes optional actions when specified."""
        include = ["ListTagsAction"]
        actions = LambdaFunctionActionsMap().merge(include)
        names = [a.__name__ for a in actions]
        assert "ListFunctionsAction" in names
        assert "ListTagsAction" in names

    def test_merge_with_list_tags_action(self) -> None:
        """Test that merge includes ListTagsAction when specified."""
        action_map = LambdaFunctionActionsMap()
        merged = action_map.merge(["ListTagsAction"])

        names = [cls.__name__ for cls in merged]
        assert "ListFunctionsAction" in names  # Default action
        assert "ListTagsAction" in names  # Optional action when specified

    def test_merge_with_nonexistent_options(self) -> None:
        """Test that merge handles nonexistent option actions gracefully."""
        action_map = LambdaFunctionActionsMap()
        merged = action_map.merge(["NonExistentAction"])

        # Should still include defaults
        names = [cls.__name__ for cls in merged]
        assert "ListFunctionsAction" in names
