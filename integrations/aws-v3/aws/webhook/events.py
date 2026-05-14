from __future__ import annotations

from enum import StrEnum
from typing import Final


WEBHOOK_PATH: Final[str] = "/webhook"
"""HTTP path on which Ocean registers the AWS live-events endpoint."""

SNS_MESSAGE_TYPE_HEADER: Final[str] = "x-amz-sns-message-type"
SNS_MESSAGE_ID_HEADER: Final[str] = "x-amz-sns-message-id"
SNS_TOPIC_ARN_HEADER: Final[str] = "x-amz-sns-topic-arn"
PORT_HMAC_HEADER: Final[str] = "x-port-signature"


class SnsMessageType(StrEnum):
    """SNS HTTPS delivery message types — set in `x-amz-sns-message-type`."""

    NOTIFICATION = "Notification"
    SUBSCRIPTION_CONFIRMATION = "SubscriptionConfirmation"
    UNSUBSCRIBE_CONFIRMATION = "UnsubscribeConfirmation"


class EventBridgeDetailType(StrEnum):
    """`detail-type` values the live-event processors route on."""

    EC2_INSTANCE_STATE_CHANGE = "EC2 Instance State-change Notification"
    ECS_SERVICE_ACTION = "ECS Service Action"
    ECS_DEPLOYMENT_STATE_CHANGE = "ECS Deployment State Change"
    CLOUDTRAIL_API_CALL = "AWS API Call via CloudTrail"


# `eventSource` values used when a kind shares the CloudTrail detail-type;
# each processor narrows further on these.
LAMBDA_EVENT_SOURCE: Final[str] = "lambda.amazonaws.com"
S3_EVENT_SOURCE: Final[str] = "s3.amazonaws.com"


# CloudTrail event names mapped to upsert vs delete semantics per kind.
LAMBDA_UPSERT_EVENT_NAMES: Final[frozenset[str]] = frozenset(
    {
        "CreateFunction20150331",
        "UpdateFunctionConfiguration20150331v2",
        "UpdateFunctionCode20150331v2",
        "PublishVersion20150331",
        "TagResource20170331v2",
        "UntagResource20170331v2",
    }
)
LAMBDA_DELETE_EVENT_NAMES: Final[frozenset[str]] = frozenset(
    {"DeleteFunction20150331"}
)


S3_UPSERT_EVENT_NAMES: Final[frozenset[str]] = frozenset(
    {
        "CreateBucket",
        "PutBucketTagging",
        "PutBucketPolicy",
        "PutBucketEncryption",
        "PutPublicAccessBlock",
        "PutBucketOwnershipControls",
    }
)
S3_DELETE_EVENT_NAMES: Final[frozenset[str]] = frozenset({"DeleteBucket"})


EC2_TERMINAL_STATES: Final[frozenset[str]] = frozenset(
    {"shutting-down", "terminated"}
)


ECS_DELETE_EVENT_NAMES: Final[frozenset[str]] = frozenset({"SERVICE_DELETED"})
