from typing import Optional, Dict
from pydantic import Field, ConfigDict
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel, BaseAWSPropertiesModel


class QueueProperties(BaseAWSPropertiesModel):
    model_config = ConfigDict(extra="forbid")

    QueueName: str = Field(default_factory=str)
    QueueUrl: str = Field(default_factory=str)
    QueueArn: Optional[str] = None
    ApproximateNumberOfMessages: Optional[int] = None
    ApproximateNumberOfMessagesNotVisible: Optional[int] = None
    ApproximateNumberOfMessagesDelayed: Optional[int] = None
    CreatedTimestamp: Optional[str] = None
    LastModifiedTimestamp: Optional[str] = None
    VisibilityTimeout: Optional[int] = None
    MaximumMessageSize: Optional[int] = None
    MessageRetentionPeriod: Optional[int] = None
    DelaySeconds: Optional[int] = None
    ReceiveMessageWaitTimeSeconds: Optional[int] = None
    Policy: Optional[str] = None
    RedrivePolicy: Optional[str] = None
    RedriveAllowPolicy: Optional[str] = None
    KmsMasterKeyId: Optional[str] = None
    KmsDataKeyReusePeriodSeconds: Optional[int] = None
    SqsManagedSseEnabled: Optional[bool] = None
    FifoQueue: Optional[bool] = None
    ContentBasedDeduplication: Optional[bool] = None
    DeduplicationScope: Optional[str] = None
    FifoThroughputLimit: Optional[str] = None
    Tags: Dict[str, str] = Field(default_factory=dict)


class Queue(ResourceModel[QueueProperties]):
    Type: str = "AWS::SQS::Queue"
    Properties: QueueProperties = Field(default_factory=QueueProperties)


class SingleQueueRequest(ResourceRequestModel):
    """Options for exporting a single SQS queue."""

    queue_url: str = Field(..., description="The URL of the SQS queue to export")


class PaginatedQueueRequest(ResourceRequestModel):
    """Options for exporting all SQS queues in a region."""

    pass
