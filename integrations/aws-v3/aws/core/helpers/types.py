from enum import StrEnum
from typing import Literal


class ObjectKind(StrEnum):
    S3_BUCKET = "AWS::S3::Bucket"
    EC2_INSTANCE = "AWS::EC2::Instance"
    ECS_CLUSTER = "AWS::ECS::Cluster"
    ORGANIZATIONS_ACCOUNT = "AWS::Organizations::Account"
    AccountInfo = "AWS::Account::Info"
    RDS_DB_INSTANCE = "AWS::RDS::DBInstance"
    EKS_CLUSTER = "AWS::EKS::Cluster"
    LAMBDA_FUNCTION = "AWS::Lambda::Function"
    ECS_SERVICE = "AWS::ECS::Service"
    ECS_TASK_DEFINITION = "AWS::ECS::TaskDefinition"
    SQS_QUEUE = "AWS::SQS::Queue"
    ECR_REPOSITORY = "AWS::ECR::Repository"
    MEMORYDB_USER = "AWS::MemoryDB::User"


SupportedServices = Literal[
    "s3",
    "ecs",
    "ec2",
    "sqs",
    "organizations",
    "eks",
    "rds",
    "lambda",
    "ecr",
    "memorydb",
]

MEMORYDB_SUPPORTED_REGIONS: frozenset[str] = frozenset(
    {
        "us-east-1",
        "us-east-2",
        "us-west-1",
        "us-west-2",
        "ap-east-1",
        "ap-south-1",
        "ap-northeast-1",
        "ap-northeast-2",
        "ap-southeast-1",
        "ap-southeast-2",
        "ca-central-1",
        "eu-central-1",
        "eu-west-1",
        "eu-west-2",
        "eu-west-3",
        "eu-south-1",
        "eu-south-2",
        "eu-north-1",
        "sa-east-1",
        "us-gov-east-1",
        "us-gov-west-1",
    }
)
