from enum import StrEnum
from typing import Literal


class ObjectKind(StrEnum):
    S3_BUCKET = "AWS::S3::Bucket"
    EC2_INSTANCE = "AWS::EC2::Instance"
    ECS_CLUSTER = "AWS::ECS::Cluster"
    ORGANIZATIONS_ACCOUNT = "AWS::Organizations::Account"
    AccountInfo = "AWS::Account::Info"
    RDS_DB_INSTANCE = "AWS::RDS::DBInstance"
    RDS_DB_CLUSTER = "AWS::RDS::DBCluster"
    EKS_CLUSTER = "AWS::EKS::Cluster"
    LAMBDA_FUNCTION = "AWS::Lambda::Function"
    ECS_SERVICE = "AWS::ECS::Service"
    ECS_TASK_DEFINITION = "AWS::ECS::TaskDefinition"
    SQS_QUEUE = "AWS::SQS::Queue"
    ECR_REPOSITORY = "AWS::ECR::Repository"
    MSK_SERVERLESS_CLUSTER = "AWS::MSK::ServerlessCluster"
    MEMORYDB_USER = "AWS::MemoryDB::User"
    MSK_CLUSTER = "AWS::MSK::Cluster"
    ELASTICACHE_CLUSTER = "AWS::ElastiCache::Cluster"
    EC2_VOLUME = "AWS::EC2::Volume"
    CODEPIPELINE_PIPELINE = "AWS::CodePipeline::Pipeline"


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
    "kafka",
    "elasticache",
    "codepipeline",
]
