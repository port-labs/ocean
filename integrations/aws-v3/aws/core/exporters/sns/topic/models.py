from pydantic import Field, ConfigDict
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
    BaseAWSPropertiesModel,
)


class TopicProperties(BaseAWSPropertiesModel):
    model_config = ConfigDict(extra="ignore")

    TopicArn: str = Field(default_factory=str)
    Owner: str | None = None
    DisplayName: str | None = None
    Policy: str | None = None
    DeliveryPolicy: str | None = None
    EffectiveDeliveryPolicy: str | None = None
    SubscriptionsConfirmed: int | None = None
    SubscriptionsDeleted: int | None = None
    SubscriptionsPending: int | None = None
    SignatureVersion: str | None = None
    TracingConfig: str | None = None
    KmsMasterKeyId: str | None = None
    FifoTopic: bool | None = None
    ContentBasedDeduplication: bool | None = None
    ArchivePolicy: str | None = None
    BeginningArchiveTime: str | None = None
    FifoThroughputScope: str | None = None
    HTTPSuccessFeedbackRoleArn: str | None = None
    HTTPSuccessFeedbackSampleRate: int | None = None
    HTTPFailureFeedbackRoleArn: str | None = None
    FirehoseSuccessFeedbackRoleArn: str | None = None
    FirehoseSuccessFeedbackSampleRate: int | None = None
    FirehoseFailureFeedbackRoleArn: str | None = None
    LambdaSuccessFeedbackRoleArn: str | None = None
    LambdaSuccessFeedbackSampleRate: int | None = None
    LambdaFailureFeedbackRoleArn: str | None = None
    ApplicationSuccessFeedbackRoleArn: str | None = None
    ApplicationSuccessFeedbackSampleRate: int | None = None
    ApplicationFailureFeedbackRoleArn: str | None = None
    SQSSuccessFeedbackRoleArn: str | None = None
    SQSSuccessFeedbackSampleRate: int | None = None
    SQSFailureFeedbackRoleArn: str | None = None
    Tags: list[dict[str, str]] | None = None


class Topic(ResourceModel[TopicProperties]):
    Type: str = "AWS::SNS::Topic"
    Properties: TopicProperties = Field(default_factory=TopicProperties)


class SingleTopicRequest(ResourceRequestModel):
    topic_arn: str = Field(..., description="The ARN of the SNS topic to export")


class PaginatedTopicRequest(ResourceRequestModel):
    pass
