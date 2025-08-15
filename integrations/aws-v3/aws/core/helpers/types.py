from enum import StrEnum
from typing import Literal


class ObjectKind(StrEnum):
    S3_BUCKET = "AWS::S3::Bucket"


SupportedServices = Literal["s3", "ecs", "ec2", "sqs"]
