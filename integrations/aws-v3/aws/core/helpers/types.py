from enum import StrEnum
from typing import Literal


class ObjectKind(StrEnum):
    S3_BUCKET = "AWS::S3::Bucket"
    ECS_CLUSTER = "AWS::ECS::Cluster"


SupportedServices = Literal["s3", "ecs"]
