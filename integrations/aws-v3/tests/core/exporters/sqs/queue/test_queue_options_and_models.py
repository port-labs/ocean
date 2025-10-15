import pytest
from pydantic import ValidationError

from aws.core.exporters.sqs.queue.models import (
    QueueProperties,
    Queue,
    SingleQueueRequest,
    PaginatedQueueRequest,
)


class TestExporterOptions:

    def test_initialization_with_required_fields(self) -> None:
        options = SingleQueueRequest(
            region="us-west-2",
            account_id="123456789012",
            queue_url="https://sqs.us-west-2.amazonaws.com/123456789012/test-queue",
        )
        assert options.region == "us-west-2"
        assert options.account_id == "123456789012"
        assert (
            options.queue_url
            == "https://sqs.us-west-2.amazonaws.com/123456789012/test-queue"
        )
        assert options.include == []

    def test_initialization_with_all_fields(self) -> None:
        include_list = ["GetQueueAttributesAction"]
        options = SingleQueueRequest(
            region="eu-central-1",
            account_id="123456789012",
            queue_url="https://sqs.eu-central-1.amazonaws.com/123456789012/test-queue",
            include=include_list,
        )
        assert options.region == "eu-central-1"
        assert options.account_id == "123456789012"
        assert (
            options.queue_url
            == "https://sqs.eu-central-1.amazonaws.com/123456789012/test-queue"
        )
        assert options.include == include_list

    def test_missing_required_region(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SingleQueueRequest(
                account_id="123456789012",
                queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            )  # type: ignore
        assert "region" in str(exc_info.value)

    def test_missing_required_queue_url(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SingleQueueRequest(
                region="us-east-1", account_id="123456789012"
            )  # type: ignore
        assert "queue_url" in str(exc_info.value)

    def test_empty_include_list(self) -> None:
        options = SingleQueueRequest(
            region="us-east-1",
            account_id="123456789012",
            queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            include=[],
        )
        assert options.region == "us-east-1"
        assert options.include == []

    def test_include_list_validation(self) -> None:
        options = SingleQueueRequest(
            region="us-east-1",
            account_id="123456789012",
            queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            include=["GetQueueAttributesAction", "GetQueueTagsAction"],
        )
        assert len(options.include) == 2
        assert "GetQueueAttributesAction" in options.include
        assert "GetQueueTagsAction" in options.include


class TestPaginatedQueueRequest:

    def test_inheritance(self) -> None:
        """Test that PaginatedQueueRequest inherits from the base class."""
        from aws.core.modeling.resource_models import ResourceRequestModel

        assert issubclass(PaginatedQueueRequest, ResourceRequestModel)

    def test_initialization_with_required_fields(self) -> None:
        options = PaginatedQueueRequest(region="us-west-2", account_id="123456789012")
        assert options.region == "us-west-2"
        assert options.account_id == "123456789012"
        assert options.include == []

    def test_initialization_with_include(self) -> None:
        include_list = ["GetQueueAttributesAction"]
        options = PaginatedQueueRequest(
            region="us-east-1",
            account_id="123456789012",
            include=include_list,
        )
        assert options.region == "us-east-1"
        assert options.account_id == "123456789012"
        assert options.include == include_list


class TestQueueProperties:

    def test_initialization_empty(self) -> None:
        """Test QueueProperties with no arguments."""
        props = QueueProperties()
        assert props.QueueName == ""
        assert props.QueueUrl == ""
        assert props.QueueArn is None
        assert props.Tags == {}
        assert props.ApproximateNumberOfMessages is None
        assert props.SqsManagedSseEnabled is None

    def test_initialization_with_properties(self) -> None:
        """Test QueueProperties with specific values."""
        props = QueueProperties(
            QueueName="test-queue",
            QueueUrl="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            QueueArn="arn:aws:sqs:us-east-1:123456789012:test-queue",
            ApproximateNumberOfMessages=5,
            SqsManagedSseEnabled=False,
        )
        assert props.QueueName == "test-queue"
        assert (
            props.QueueUrl
            == "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
        )
        assert props.QueueArn == "arn:aws:sqs:us-east-1:123456789012:test-queue"
        assert props.ApproximateNumberOfMessages == 5
        assert props.SqsManagedSseEnabled is False

    def test_all_properties_assignment(self) -> None:
        """Test that all properties can be assigned."""
        props = QueueProperties(
            QueueName="test-queue",
            QueueUrl="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            QueueArn="arn:aws:sqs:us-east-1:123456789012:test-queue",
            ApproximateNumberOfMessages=10,
            ApproximateNumberOfMessagesNotVisible=2,
            ApproximateNumberOfMessagesDelayed=1,
            CreatedTimestamp="1609459200",
            LastModifiedTimestamp="1609462800",
            VisibilityTimeout=30,  # This uses the alias
            MessageRetentionPeriod=345600,
            DelaySeconds=0,
            ReceiveMessageWaitTimeSeconds=0,
            MaximumMessageSize=262144,
            RedriveAllowPolicy='{"test": "policy"}',
            SqsManagedSseEnabled=True,
            Tags={"Environment": "Production"},
        )

        # Verify all properties are set correctly
        assert props.QueueName == "test-queue"
        assert (
            props.QueueUrl
            == "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
        )
        assert props.QueueArn == "arn:aws:sqs:us-east-1:123456789012:test-queue"
        assert props.ApproximateNumberOfMessages == 10
        assert props.SqsManagedSseEnabled is True
        assert props.Tags == {"Environment": "Production"}

    def test_dict_exclude_none(self) -> None:
        """Test that dict() excludes None values."""
        props = QueueProperties(
            QueueName="test-queue",
            QueueUrl="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            QueueArn="arn:aws:sqs:us-east-1:123456789012:test-queue",
        )

        props_dict = props.dict(exclude_none=True)

        # Should not include None values
        assert "ApproximateNumberOfMessages" not in props_dict
        assert "SqsManagedSseEnabled" not in props_dict

        # Should include set values
        assert props_dict["QueueName"] == "test-queue"
        assert (
            props_dict["QueueUrl"]
            == "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
        )
        assert props_dict["QueueArn"] == "arn:aws:sqs:us-east-1:123456789012:test-queue"


class TestQueue:

    def test_initialization_with_identifier(self) -> None:
        """Test Queue initialization with identifier."""
        queue = Queue()
        assert queue.Type == "AWS::SQS::Queue"
        assert queue.Properties is not None

    def test_initialization_with_properties(self) -> None:
        """Test Queue initialization with properties."""
        props = QueueProperties(
            QueueName="test-queue",
            QueueUrl="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            QueueArn="arn:aws:sqs:us-east-1:123456789012:test-queue",
        )
        queue = Queue(Properties=props)
        assert queue.Type == "AWS::SQS::Queue"
        assert queue.Properties.QueueName == "test-queue"

    def test_type_is_fixed(self) -> None:
        """Test that the type field is fixed."""
        queue = Queue()
        assert queue.Type == "AWS::SQS::Queue"

    def test_dict_exclude_none(self) -> None:
        """Test that dict() excludes None values."""
        queue = Queue()
        queue_dict = queue.dict(exclude_none=True)
        assert "Properties" not in queue_dict or queue_dict["Properties"] is not None

    def test_properties_default_factory(self) -> None:
        """Test that properties has a default factory."""
        queue1 = Queue()
        queue2 = Queue()

        # Properties should be different instances
        assert queue1.Properties is not queue2.Properties
