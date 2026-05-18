"""Constants describing the EventBridge envelopes the AWS-V3 integration consumes.

Centralizing the magic strings here keeps the per-kind processors small and
gives the test suite one source of truth for fixtures.
"""

from __future__ import annotations

EVENT_BRIDGE_CT_DETAIL_TYPE = "AWS API Call via CloudTrail"


EC2_SOURCE = "aws.ec2"
EC2_DETAIL_TYPE = "EC2 Instance State-change Notification"
EC2_TERMINAL_STATES: frozenset[str] = frozenset({"shutting-down", "terminated"})


ECS_SOURCE = "aws.ecs"
ECS_DETAIL_TYPES: frozenset[str] = frozenset(
    {"ECS Service Action", "ECS Deployment State Change"}
)
ECS_SERVICE_DELETED_EVENT_NAME = "SERVICE_DELETED"


LAMBDA_SOURCE = "aws.lambda"
LAMBDA_EVENT_SOURCE = "lambda.amazonaws.com"
LAMBDA_UPSERT_EVENT_NAME_PREFIXES: tuple[str, ...] = (
    "CreateFunction20",
    "UpdateFunctionConfiguration20",
    "UpdateFunctionCode20",
)
LAMBDA_DELETE_EVENT_NAME_PREFIX = "DeleteFunction20"


S3_SOURCE = "aws.s3"
S3_EVENT_SOURCE = "s3.amazonaws.com"
S3_CREATE_BUCKET_EVENT_NAME = "CreateBucket"
S3_DELETE_BUCKET_EVENT_NAME = "DeleteBucket"
S3_DEFAULT_REGION = "us-east-1"
