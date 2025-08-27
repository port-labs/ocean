from enum import StrEnum
from typing import Literal


class ObjectKind(StrEnum):
    S3_BUCKET = "AWS::S3::Bucket"
    ECS_CLUSTER = "AWS::ECS::Cluster"
    AWS_ACCOUNT = "AWS::Organizations::Account"


SupportedServices = Literal["s3", "ecs", "ec2", "sqs", "organizations"]
