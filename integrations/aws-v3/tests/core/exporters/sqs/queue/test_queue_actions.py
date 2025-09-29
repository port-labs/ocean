from typing import Any
from unittest.mock import AsyncMock
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.sqs.queue.actions import (
    GetQueueAttributesAction,
    GetQueueTagsAction,
    ListQueuesAction,
    SqsQueueActionsMap,
)
from aws.core.interfaces.action import Action


class TestGetQueueAttributesAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock SQS client for testing."""
        mock_client = AsyncMock()
        mock_client.get_queue_attributes = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetQueueAttributesAction:
        """Create a GetQueueAttributesAction instance for testing."""
        return GetQueueAttributesAction(mock_client)

    def test_inheritance(self, action: GetQueueAttributesAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: GetQueueAttributesAction) -> None:
        """Test successful execution of get_queue_attributes."""
        # Mock response
        expected_response = {
            "Attributes": {
                "QueueArn": "arn:aws:sqs:us-east-1:123456789012:test-queue",
                "ApproximateNumberOfMessages": "5",
                "ApproximateNumberOfMessagesNotVisible": "2",
                "ApproximateNumberOfMessagesDelayed": "0",
                "CreatedTimestamp": "1609459200",
                "LastModifiedTimestamp": "1609462800",
                "VisibilityTimeout": "30",
                "MessageRetentionPeriod": "345600",
                "DelaySeconds": "0",
                "ReceiveMessageWaitTimeSeconds": "0",
                "FifoQueue": "false",
            }
        }
        action.client.get_queue_attributes.return_value = expected_response

        test_queue_urls = [
            "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
        ]
        result = await action._execute(test_queue_urls)

        assert len(result) == 1
        assert result[0]["QueueArn"] == "arn:aws:sqs:us-east-1:123456789012:test-queue"
        assert result[0]["ApproximateNumberOfMessages"] == "5"
        assert result[0]["VisibilityTimeout"] == "30"

        action.client.get_queue_attributes.assert_called_once_with(
            QueueUrl="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            AttributeNames=["All"],
        )

    @pytest.mark.asyncio
    async def test_execute_empty_list(self, action: GetQueueAttributesAction) -> None:
        """Test execution with empty queue list."""
        result = await action._execute([])

        assert result == []
        action.client.get_queue_attributes.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_with_recoverable_exception(
        self, action: GetQueueAttributesAction
    ) -> None:
        """Test execution with recoverable exception."""
        # Mock ClientError for resource not found
        error = ClientError(
            error_response={"Error": {"Code": "ResourceNotFound"}},
            operation_name="GetQueueAttributes",
        )
        action.client.get_queue_attributes.side_effect = error

        test_queue_urls = [
            "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
        ]
        result = await action._execute(test_queue_urls)

        # Should return empty list since the exception is recoverable
        assert result == []
        action.client.get_queue_attributes.assert_called_once_with(
            QueueUrl="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            AttributeNames=["All"],
        )

    @pytest.mark.asyncio
    async def test_execute_with_non_recoverable_exception(
        self, action: GetQueueAttributesAction
    ) -> None:
        """Test execution with non-recoverable exception."""
        # Mock ClientError for non-recoverable exception
        error = ClientError(
            error_response={"Error": {"Code": "InvalidParameterValue"}},
            operation_name="GetQueueAttributes",
        )
        action.client.get_queue_attributes.side_effect = error

        test_queue_urls = [
            "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
        ]

        # This should raise the exception since it's non-recoverable
        with pytest.raises(ClientError):
            await action._execute(test_queue_urls)


class TestGetQueueTagsAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock SQS client for testing."""
        mock_client = AsyncMock()
        mock_client.list_queue_tags = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetQueueTagsAction:
        """Create a GetQueueTagsAction instance for testing."""
        return GetQueueTagsAction(mock_client)

    def test_inheritance(self, action: GetQueueTagsAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: GetQueueTagsAction) -> None:
        """Test successful execution of list_queue_tags."""
        # Mock response
        expected_response = {"Tags": {"Environment": "Production", "Team": "Backend"}}
        action.client.list_queue_tags.return_value = expected_response

        test_queue_urls = [
            "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
        ]
        result = await action._execute(test_queue_urls)

        assert len(result) == 1
        assert result[0]["Tags"]["Environment"] == "Production"
        assert result[0]["Tags"]["Team"] == "Backend"

        action.client.list_queue_tags.assert_called_once_with(
            QueueUrl="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
        )

    @pytest.mark.asyncio
    async def test_execute_no_tags(self, action: GetQueueTagsAction) -> None:
        """Test execution with no tags."""
        # Mock response with no tags
        expected_response: dict[str, Any] = {"Tags": {}}
        action.client.list_queue_tags.return_value = expected_response

        test_queue_urls = [
            "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
        ]
        result = await action._execute(test_queue_urls)

        assert len(result) == 1
        assert result[0]["Tags"] == {}

        action.client.list_queue_tags.assert_called_once_with(
            QueueUrl="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
        )

    @pytest.mark.asyncio
    async def test_execute_with_recoverable_exception(
        self, action: GetQueueTagsAction
    ) -> None:
        """Test execution with recoverable exception."""
        # Mock ClientError for access denied
        error = ClientError(
            error_response={"Error": {"Code": "AccessDenied"}},
            operation_name="ListQueueTags",
        )
        action.client.list_queue_tags.side_effect = error

        test_queue_urls = [
            "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
        ]
        result = await action._execute(test_queue_urls)

        # Should return empty list since the exception is recoverable
        assert result == []
        action.client.list_queue_tags.assert_called_once_with(
            QueueUrl="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
        )

    @pytest.mark.asyncio
    async def test_execute_with_non_recoverable_exception(
        self, action: GetQueueTagsAction
    ) -> None:
        """Test execution with non-recoverable exception."""
        # Mock ClientError for non-recoverable exception
        error = ClientError(
            error_response={"Error": {"Code": "InvalidParameterValue"}},
            operation_name="ListQueueTags",
        )
        action.client.list_queue_tags.side_effect = error

        test_queue_urls = [
            "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
        ]

        # This should raise the exception since it's non-recoverable
        with pytest.raises(ClientError):
            await action._execute(test_queue_urls)


class TestListQueuesAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create a mock SQS client for testing."""
        return AsyncMock()

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> ListQueuesAction:
        """Create a ListQueuesAction instance for testing."""
        return ListQueuesAction(mock_client)

    def test_inheritance(self, action: ListQueuesAction) -> None:
        """Test that the action inherits from Action."""
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: ListQueuesAction) -> None:
        """Test successful execution of list queues (pass-through)."""
        test_queue_urls = [
            "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue-1",
            "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue-2.fifo",
        ]

        result = await action._execute(test_queue_urls)

        assert len(result) == 2
        assert (
            result[0]["QueueUrl"]
            == "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue-1"
        )
        assert (
            result[1]["QueueUrl"]
            == "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue-2.fifo"
        )

    @pytest.mark.asyncio
    async def test_execute_empty_list(self, action: ListQueuesAction) -> None:
        """Test execution with empty queue list."""
        result = await action._execute([])
        assert result == []


class TestSqsQueueActionsMap:

    def test_merge_includes_defaults(self) -> None:
        """Test that merge includes default actions."""
        actions_map = SqsQueueActionsMap()
        assert ListQueuesAction in actions_map.defaults
        assert GetQueueAttributesAction in actions_map.defaults
        assert GetQueueTagsAction in actions_map.defaults

    def test_merge_with_options(self) -> None:
        """Test that merge works with options."""
        actions_map = SqsQueueActionsMap()
        # For now, there are no optional actions, but this tests the structure
        assert actions_map.options == []
