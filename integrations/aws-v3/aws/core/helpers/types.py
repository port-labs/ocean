from enum import StrEnum
from typing import Literal


class ObjectKind(StrEnum):
    S3_BUCKET = "AWS::S3::Bucket"
    EC2_INSTANCE = "AWS::EC2::Instance"
    ORGANIZATIONS_ACCOUNT = "AWS::Organizations::Account"
    AccountInfo = "AWS::Account::Info"
    ECS_CLUSTER = "AWS::ECS::Cluster"
    SQS_QUEUE = "AWS::SQS::Queue"


SupportedServices = Literal["s3", "ecs", "ec2", "sqs", "organizations"]
