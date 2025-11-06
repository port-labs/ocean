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
    SQS_QUEUE = "AWS::SQS::Queue"
    API_GATEWAY_REST_API = "AWS::ApiGateway::RestApi"


SupportedServices = Literal[
    "s3", "ecs", "ec2", "sqs", "organizations", "eks", "rds", "lambda", "apigateway"
]
