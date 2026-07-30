import pytest
from pydantic import ValidationError

from aws.core.exporters.sns.topic.models import (
    TopicProperties,
    Topic,
    SingleTopicRequest,
    PaginatedTopicRequest,
)


class TestTopicProperties:

    def test_initialization_empty(self) -> None:
        props = TopicProperties()
        assert props.TopicArn == ""
        assert props.TopicName == ""
        assert props.Owner is None
        assert props.DisplayName is None
        assert props.SubscriptionsConfirmed is None
        assert props.FifoTopic is None
        assert props.Tags is None

    def test_initialization_standard_topic(self) -> None:
        props = TopicProperties(
            TopicArn="arn:aws:sns:us-east-1:123456789012:my-topic",
            TopicName="my-topic",
            Owner="123456789012",
            DisplayName="My Topic",
            SubscriptionsConfirmed=3,
            SubscriptionsDeleted=0,
            SubscriptionsPending=1,
            SignatureVersion="1",
            TracingConfig="PassThrough",
        )
        assert props.TopicArn == "arn:aws:sns:us-east-1:123456789012:my-topic"
        assert props.TopicName == "my-topic"
        assert props.Owner == "123456789012"
        assert props.SubscriptionsConfirmed == 3
        assert props.TracingConfig == "PassThrough"
        assert props.FifoTopic is None

    def test_initialization_fifo_topic(self) -> None:
        props = TopicProperties(
            TopicArn="arn:aws:sns:us-east-1:123456789012:my-topic.fifo",
            TopicName="my-topic.fifo",
            Owner="123456789012",
            FifoTopic=True,
            ContentBasedDeduplication=True,
            FifoThroughputScope="Topic",
        )
        assert props.FifoTopic is True
        assert props.ContentBasedDeduplication is True
        assert props.FifoThroughputScope == "Topic"

    def test_string_to_int_coercion(self) -> None:
        props = TopicProperties(
            SubscriptionsConfirmed="42",  # type: ignore[arg-type]
            SubscriptionsDeleted="0",  # type: ignore[arg-type]
            SubscriptionsPending="5",  # type: ignore[arg-type]
        )
        assert props.SubscriptionsConfirmed == 42
        assert props.SubscriptionsDeleted == 0
        assert props.SubscriptionsPending == 5

    def test_string_to_bool_coercion(self) -> None:
        props = TopicProperties(
            FifoTopic="true",  # type: ignore[arg-type]
            ContentBasedDeduplication="false",  # type: ignore[arg-type]
        )
        assert props.FifoTopic is True
        assert props.ContentBasedDeduplication is False

    def test_delivery_feedback_fields(self) -> None:
        props = TopicProperties(
            HTTPSuccessFeedbackRoleArn="arn:aws:iam::123456789012:role/sns-feedback",
            HTTPSuccessFeedbackSampleRate=100,
            HTTPFailureFeedbackRoleArn="arn:aws:iam::123456789012:role/sns-feedback",
            LambdaSuccessFeedbackRoleArn="arn:aws:iam::123456789012:role/lambda-feedback",
        )
        assert props.HTTPSuccessFeedbackSampleRate == 100
        assert props.LambdaSuccessFeedbackRoleArn is not None

    def test_extra_forbid_rejects_unknown_fields(self) -> None:
        with pytest.raises(ValidationError):
            TopicProperties(UnknownField="value")  # type: ignore[call-arg]

    def test_tags_format(self) -> None:
        props = TopicProperties(
            Tags=[
                {"Key": "Environment", "Value": "Production"},
                {"Key": "Team", "Value": "Backend"},
            ]
        )
        assert len(props.Tags) == 2  # type: ignore[arg-type]
        assert props.Tags[0]["Key"] == "Environment"  # type: ignore[index]

    def test_dict_exclude_none(self) -> None:
        props = TopicProperties(
            TopicArn="arn:aws:sns:us-east-1:123456789012:my-topic",
            TopicName="my-topic",
        )
        props_dict = props.model_dump(exclude_none=True)
        assert "Owner" not in props_dict
        assert "FifoTopic" not in props_dict
        assert props_dict["TopicArn"] == "arn:aws:sns:us-east-1:123456789012:my-topic"


class TestTopic:

    def test_default_type(self) -> None:
        topic = Topic()
        assert topic.Type == "AWS::SNS::Topic"

    def test_initialization_with_properties(self) -> None:
        props = TopicProperties(
            TopicArn="arn:aws:sns:us-east-1:123456789012:my-topic",
            TopicName="my-topic",
        )
        topic = Topic(Properties=props)
        assert topic.Type == "AWS::SNS::Topic"
        assert topic.Properties.TopicName == "my-topic"

    def test_properties_default_factory(self) -> None:
        topic1 = Topic()
        topic2 = Topic()
        assert topic1.Properties is not topic2.Properties


class TestSingleTopicRequest:

    def test_initialization_with_required_fields(self) -> None:
        request = SingleTopicRequest(
            region="us-east-1",
            account_id="123456789012",
            topic_arn="arn:aws:sns:us-east-1:123456789012:my-topic",
        )
        assert request.region == "us-east-1"
        assert request.account_id == "123456789012"
        assert request.topic_arn == "arn:aws:sns:us-east-1:123456789012:my-topic"
        assert request.include == []

    def test_missing_required_topic_arn(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SingleTopicRequest(
                region="us-east-1", account_id="123456789012"
            )  # type: ignore
        assert "topic_arn" in str(exc_info.value)

    def test_with_include(self) -> None:
        request = SingleTopicRequest(
            region="us-east-1",
            account_id="123456789012",
            topic_arn="arn:aws:sns:us-east-1:123456789012:my-topic",
            include=["GetTopicTagsAction"],
        )
        assert request.include == ["GetTopicTagsAction"]


class TestPaginatedTopicRequest:

    def test_inheritance(self) -> None:
        from aws.core.modeling.resource_models import ResourceRequestModel

        assert issubclass(PaginatedTopicRequest, ResourceRequestModel)

    def test_initialization(self) -> None:
        request = PaginatedTopicRequest(region="us-east-1", account_id="123456789012")
        assert request.region == "us-east-1"
        assert request.account_id == "123456789012"
        assert request.include == []
