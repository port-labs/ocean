from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class QueueProperties(BaseModel):
    QueueName: str = Field(default_factory=str)
    QueueUrl: str = Field(default_factory=str)
    Arn: str = Field(default_factory=str)
    ApproximateNumberOfMessages: Optional[int] = None
    ApproximateNumberOfMessagesNotVisible: Optional[int] = None
    ApproximateNumberOfMessagesDelayed: Optional[int] = None
    CreatedTimestamp: Optional[str] = None
    LastModifiedTimestamp: Optional[str] = None
    VisibilityTimeoutSeconds: Optional[int] = None
    MaxReceiveCount: Optional[int] = None
    MessageRetentionPeriod: Optional[int] = None
    DelaySeconds: Optional[int] = None
    ReceiveMessageWaitTimeSeconds: Optional[int] = None
    KmsMasterKeyId: Optional[str] = None
    KmsDataKeyReusePeriodSeconds: Optional[int] = None
    SqsManagedSseEnabled: Optional[bool] = None
    FifoQueue: Optional[bool] = None
    ContentBasedDeduplication: Optional[bool] = None
    DeduplicationScope: Optional[str] = None
    FifoThroughputLimit: Optional[str] = None
    Tags: List[Dict[str, Any]] = Field(default_factory=list)

    # Optional fields for dead letter queue
    RedrivePolicy: Optional[Dict[str, Any]] = None
    RedriveAllowPolicy: Optional[Dict[str, Any]] = None

    class Config:
        extra = "forbid"
        populate_by_name = True


class Queue(ResourceModel[QueueProperties]):
    Type: str = "AWS::SQS::Queue"
    Properties: QueueProperties = Field(default_factory=QueueProperties)


class SingleQueueRequest(ResourceRequestModel):
    """Options for exporting a single SQS queue."""
    
    queue_url: str = Field(..., description="The URL of the SQS queue to export")


class PaginatedQueueRequest(ResourceRequestModel):
    """Options for exporting all SQS queues in a region."""
    pass