from pydantic.v1 import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class QueueProperties(BaseModel):
    QueueName: str = Field(default_factory=str)
    QueueUrl: str = Field(default_factory=str)
    QueueArn: str | None = None
    ApproximateNumberOfMessages: int | None = None
    ApproximateNumberOfMessagesNotVisible: int | None = None
    ApproximateNumberOfMessagesDelayed: int | None = None
    CreatedTimestamp: str | None = None
    LastModifiedTimestamp: str | None = None
    VisibilityTimeout: int | None = None
    MaximumMessageSize: int | None = None
    MessageRetentionPeriod: int | None = None
    DelaySeconds: int | None = None
    ReceiveMessageWaitTimeSeconds: int | None = None
    Policy: str | None = None
    RedrivePolicy: str | None = None
    RedriveAllowPolicy: str | None = None
    KmsMasterKeyId: str | None = None
    KmsDataKeyReusePeriodSeconds: int | None = None
    SqsManagedSseEnabled: bool | None = None
    FifoQueue: bool | None = None
    ContentBasedDeduplication: bool | None = None
    DeduplicationScope: str | None = None
    FifoThroughputLimit: str | None = None
    Tags: dict[str, str] = Field(default_factory=dict)

    class Config:
        extra = "forbid"
        allow_population_by_field_name = True


class Queue(ResourceModel[QueueProperties]):
    Type: str = "AWS::SQS::Queue"
    Properties: QueueProperties = Field(default_factory=QueueProperties)


class SingleQueueRequest(ResourceRequestModel):
    """Options for exporting a single SQS queue."""

    queue_url: str = Field(..., description="The URL of the SQS queue to export")


class PaginatedQueueRequest(ResourceRequestModel):
    """Options for exporting all SQS queues in a region."""

    pass
