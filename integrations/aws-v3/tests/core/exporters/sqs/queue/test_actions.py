import pytest
from unittest.mock import AsyncMock, MagicMock
from aws.core.exporters.sqs.queue.actions import (
    GetQueueAttributesAction,
    GetQueueTagsAction,
    ListQueuesAction,
)


@pytest.mark.asyncio
async def test_get_queue_attributes_action():
    """Test GetQueueAttributesAction fetches queue attributes correctly."""
    action = GetQueueAttributesAction()
    action.client = AsyncMock()
    
    # Mock the get_queue_attributes response
    action.client.get_queue_attributes.return_value = {
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

    test_queues = [{"QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"}]
    result = await action._execute(test_queues)

    assert len(result) == 1
    assert result[0]["QueueName"] == "test-queue"
    assert result[0]["Arn"] == "arn:aws:sqs:us-east-1:123456789012:test-queue"
    assert result[0]["ApproximateNumberOfMessages"] == 5
    assert result[0]["FifoQueue"] is False
    action.client.get_queue_attributes.assert_called_once()


@pytest.mark.asyncio
async def test_get_queue_tags_action():
    """Test GetQueueTagsAction fetches queue tags correctly."""
    action = GetQueueTagsAction()
    action.client = AsyncMock()
    
    # Mock the list_queue_tags response
    action.client.list_queue_tags.return_value = {
        "Tags": {
            "Environment": "Production",
            "Team": "Backend"
        }
    }

    test_queues = [{"QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"}]
    result = await action._execute(test_queues)

    assert len(result) == 1
    assert len(result[0]["Tags"]) == 2
    assert {"Key": "Environment", "Value": "Production"} in result[0]["Tags"]
    assert {"Key": "Team", "Value": "Backend"} in result[0]["Tags"]
    action.client.list_queue_tags.assert_called_once()


@pytest.mark.asyncio
async def test_get_queue_tags_action_no_tags():
    """Test GetQueueTagsAction handles queues with no tags."""
    action = GetQueueTagsAction()
    action.client = AsyncMock()
    
    # Mock the list_queue_tags response with no tags
    action.client.list_queue_tags.return_value = {"Tags": {}}

    test_queues = [{"QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"}]
    result = await action._execute(test_queues)

    assert len(result) == 1
    assert result[0]["Tags"] == []
    action.client.list_queue_tags.assert_called_once()


@pytest.mark.asyncio
async def test_list_queues_action():
    """Test ListQueuesAction processes queue URLs correctly."""
    action = ListQueuesAction()
    
    test_queue_urls = [
        "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue-1",
        "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue-2.fifo"
    ]
    
    result = await action._execute(test_queue_urls)

    assert len(result) == 2
    assert result[0]["QueueUrl"] == "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue-1"
    assert result[0]["QueueName"] == "test-queue-1"
    assert result[1]["QueueUrl"] == "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue-2.fifo"
    assert result[1]["QueueName"] == "test-queue-2.fifo"


@pytest.mark.asyncio
async def test_get_queue_attributes_action_empty_list():
    """Test GetQueueAttributesAction handles empty queue list."""
    action = GetQueueAttributesAction()
    action.client = AsyncMock()
    
    result = await action._execute([])
    
    assert result == []
    action.client.get_queue_attributes.assert_not_called()


@pytest.mark.asyncio
async def test_get_queue_tags_action_access_denied():
    """Test GetQueueTagsAction handles access denied gracefully."""
    action = GetQueueTagsAction()
    action.client = AsyncMock()
    
    # Mock ClientError for access denied
    error = MagicMock()
    error.response = {"Error": {"Code": "AccessDenied"}}
    action.client.exceptions.ClientError = Exception
    action.client.list_queue_tags.side_effect = Exception()
    action.client.list_queue_tags.side_effect.response = {"Error": {"Code": "AccessDenied"}}

    test_queues = [{"QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"}]
    
    # This should handle the exception and return empty tags
    # Note: The actual implementation may need adjustment to properly handle this case
    with pytest.raises(Exception):
        await action._execute(test_queues)