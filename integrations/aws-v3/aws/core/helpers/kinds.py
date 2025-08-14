from enum import StrEnum


class ObjectKind(StrEnum):
    S3_BUCKET = "AWS::S3::Bucket"
    ECS_CLUSTER = "AWS::ECS::Cluster"
