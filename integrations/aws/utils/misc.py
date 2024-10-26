import enum

from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
import asyncio


def get_semaphore() -> asyncio.BoundedSemaphore:
    max_concurrent_accounts: int = int(
        ocean.integration_config["maximum_concurrent_accounts"]
    )
    semaphore = asyncio.BoundedSemaphore(max_concurrent_accounts)
    return semaphore


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


def is_access_denied_exception(e: Exception) -> bool:
    access_denied_error_codes = [
        "AccessDenied",
        "AccessDeniedException",
        "UnauthorizedOperation",
    ]

    if hasattr(e, "response") and e.response is not None:
        error_code = e.response.get("Error", {}).get("Code")
        return error_code in access_denied_error_codes

    return False


def is_server_error(e: Exception) -> bool:
    if hasattr(e, "response"):
        status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        return status >= 500

    return False


def get_matching_kinds_and_blueprints_from_config(
    kind: str, region: str
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    allowed_kinds: dict[str, list[str]] = {}
    disallowed_kinds: dict[str, list[str]] = {}
    resources = event.port_app_config.resources

    for resource in resources:
        blueprint = resource.port.entity.mappings.blueprint.strip('"')
        if not resource.selector.is_region_allowed(region) and kind == resource.kind:
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
