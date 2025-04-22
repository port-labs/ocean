import enum


from port_ocean.context.ocean import ocean
from utils.overrides import AWSResourceConfig
from typing import Protocol, List, Literal, Dict, Any


class CloudControlClientProtocol(Protocol):
    async def get_resource(
        self, *, TypeName: str, Identifier: str
    ) -> Dict[str, Any]: ...

    async def list_resources(
        self, *, TypeName: str, NextToken: str | None = None
    ) -> Dict[str, Any]: ...


class CloudControlThrottlingConfig(enum.Enum):
    MAX_RETRY_ATTEMPTS: int = 100
    RETRY_MODE: Literal["legacy", "standard", "adaptive"] = "adaptive"


class CustomProperties(enum.StrEnum):
    ACCOUNT_ID = "__AccountId"
    KIND = "__Kind"
    REGION = "__Region"


class ResourceKindsWithSpecialHandling(enum.StrEnum):
    ACCOUNT = "AWS::Organizations::Account"
    AMI_IMAGE = "AWS::ImageBuilder::Image"
    ACM_CERTIFICATE = "AWS::ACM::Certificate"
    CLOUDFORMATION_STACK = "AWS::CloudFormation::Stack"
    ELASTICACHE_CLUSTER = "AWS::ElastiCache::Cluster"
    ELBV2_LOAD_BALANCER = "AWS::ELBV2::LoadBalancer"
    SQS_QUEUE = "AWS::SQS::Queue"


def get_matching_kinds_and_blueprints_from_config(
    kind: str, region: str, resource_configs: List[AWSResourceConfig]
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    allowed_kinds: dict[str, list[str]] = {}
    disallowed_kinds: dict[str, list[str]] = {}
    for resource in resource_configs:
        blueprint = resource.port.entity.mappings.blueprint.strip('"')
        resource_selector = resource.selector
        if not resource_selector.is_region_allowed(region) and kind == resource.kind:
            if kind in disallowed_kinds:
                disallowed_kinds[kind].append(blueprint)
            else:
                disallowed_kinds[kind] = [blueprint]
        elif kind == resource.kind:
            if kind in allowed_kinds:
                allowed_kinds[kind].append(blueprint)
            else:
                allowed_kinds[kind] = [blueprint]

    return allowed_kinds, disallowed_kinds
