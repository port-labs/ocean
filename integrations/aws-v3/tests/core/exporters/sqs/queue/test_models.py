import pytest
from pydantic import ValidationError
from aws.core.exporters.sqs.queue.models import (
    QueueProperties,
    Queue,
    SingleQueueRequest,
    PaginatedQueueRequest,
)


def test_queue_properties_defaults():
    """Test QueueProperties with default values."""
    props = QueueProperties()
    
    assert props.QueueName == ""
    assert props.QueueUrl == ""
    assert props.Arn == ""
    assert props.Tags == []
    assert props.ApproximateNumberOfMessages is None
    assert props.FifoQueue is None


def test_queue_properties_with_values():
    """Test QueueProperties with specific values."""
    props = QueueProperties(
        QueueName="test-queue",
        QueueUrl="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
        Arn="arn:aws:sqs:us-east-1:123456789012:test-queue",
        ApproximateNumberOfMessages=5,
        FifoQueue=False,
        Tags=[{"Key": "Environment", "Value": "Test"}]
    )
    
    assert props.QueueName == "test-queue"
    assert props.QueueUrl == "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    assert props.Arn == "arn:aws:sqs:us-east-1:123456789012:test-queue"
    assert props.ApproximateNumberOfMessages == 5
    assert props.FifoQueue is False
    assert len(props.Tags) == 1
    assert props.Tags[0]["Key"] == "Environment"


def test_queue_fifo_properties():
    """Test FIFO-specific queue properties."""
    props = QueueProperties(
        QueueName="test-queue.fifo",
        FifoQueue=True,
        ContentBasedDeduplication=True,
        DeduplicationScope="messageGroup",
        FifoThroughputLimit="perMessageGroupId"
    )
    
    assert props.QueueName == "test-queue.fifo"
    assert props.FifoQueue is True
    assert props.ContentBasedDeduplication is True
    assert props.DeduplicationScope == "messageGroup"
    assert props.FifoThroughputLimit == "perMessageGroupId"


def test_queue_model():
    """Test the Queue model."""
    queue = Queue()
    
    assert queue.Type == "AWS::SQS::Queue"
    assert isinstance(queue.Properties, QueueProperties)


def test_queue_model_with_properties():
    """Test Queue model with custom properties."""
    props = QueueProperties(QueueName="test-queue")
    queue = Queue(Properties=props)
    
    assert queue.Type == "AWS::SQS::Queue"
    assert queue.Properties.QueueName == "test-queue"


def test_single_queue_request():
    """Test SingleQueueRequest model."""
    request = SingleQueueRequest(
        queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
        region="us-east-1",
        include=["GetQueueAttributesAction"],
        account_id="123456789012"
    )
    
    assert request.queue_url == "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    assert request.region == "us-east-1"
    assert request.account_id == "123456789012"


def test_single_queue_request_missing_queue_url():
    """Test SingleQueueRequest raises validation error when queue_url is missing."""
    with pytest.raises(ValidationError) as excinfo:
        SingleQueueRequest(
            region="us-east-1",
            include=[],
            account_id="123456789012"
        )
    
    assert "queue_url" in str(excinfo.value)


def test_paginated_queue_request():
    """Test PaginatedQueueRequest model."""
    request = PaginatedQueueRequest(
        region="us-east-1",
        include=["GetQueueAttributesAction"],
        account_id="123456789012"
    )
    
    assert request.region == "us-east-1"
    assert request.account_id == "123456789012"


def test_queue_properties_encryption():
    """Test queue properties with encryption settings."""
    props = QueueProperties(
        QueueName="encrypted-queue",
        KmsMasterKeyId="arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012",
        KmsDataKeyReusePeriodSeconds=300,
        SqsManagedSseEnabled=True
    )
    
    assert props.QueueName == "encrypted-queue"
    assert "key/12345678-1234-1234-1234-123456789012" in props.KmsMasterKeyId
    assert props.KmsDataKeyReusePeriodSeconds == 300
    assert props.SqsManagedSseEnabled is True


def test_queue_properties_dead_letter_queue():
    """Test queue properties with dead letter queue configuration."""
    redrive_policy = {
        "deadLetterTargetArn": "arn:aws:sqs:us-east-1:123456789012:dead-letter-queue",
        "maxReceiveCount": 3
    }
    
    props = QueueProperties(
        QueueName="main-queue",
        MaxReceiveCount=3,
        RedrivePolicy=redrive_policy
    )
    
    assert props.QueueName == "main-queue"
    assert props.MaxReceiveCount == 3
    assert props.RedrivePolicy == redrive_policy
    assert props.RedrivePolicy["maxReceiveCount"] == 3