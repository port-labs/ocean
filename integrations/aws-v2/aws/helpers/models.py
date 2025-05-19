from typing import Any, Protocol, runtime_checkable, TypedDict, Literal
from enum import StrEnum, Enum

AWS_RAW_ITEM = dict[str, Any]


class CustomProperties(StrEnum):
    ACCOUNT_ID = "__AccountId"
    KIND = "__Kind"
    REGION = "__Region"


class MaterializedResource(TypedDict):
    """A dictionary type that must have a 'CustomProperties' key."""

    CustomProperties.KIND
    CustomProperties.ACCOUNT_ID
    CustomProperties.REGION


@runtime_checkable
class CloudControlClientProtocol(Protocol):
    async def get_resource(
        self, *, TypeName: str, Identifier: str
    ) -> dict[str, Any]: ...

    async def list_resources(
        self, *, TypeName: str, **kwargs: Any
    ) -> dict[str, Any]: ...


class CloudControlThrottlingConfig(Enum):
    MAX_RETRY_ATTEMPTS: int = 100
    RETRY_MODE: Literal["legacy", "standard", "adaptive"] = "adaptive"


class ResourceKindsWithSpecialHandling(StrEnum):
    ACCOUNT = "AWS::Organizations::Account"
    AMI_IMAGE = "AWS::ImageBuilder::Image"
    ACM_CERTIFICATE = "AWS::ACM::Certificate"
    CLOUDFORMATION_STACK = "AWS::CloudFormation::Stack"
    ELASTICACHE_CLUSTER = "AWS::ElastiCache::Cluster"
    ELBV2_LOAD_BALANCER = "AWS::ELBV2::LoadBalancer"
    SQS_QUEUE = "AWS::SQS::Queue"
