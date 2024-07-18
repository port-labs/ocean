import enum

from port_ocean.context.event import event


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

    if hasattr(e, "response"):
        error_code = e.response.get("Error", {}).get("Code")
        return error_code in access_denied_error_codes

    return False


def get_matching_kinds_and_blueprints_from_config(
    kind: str,
) -> dict[str, list[str]]:
    kinds: dict[str, list[str]] = {}
    resources = event.port_app_config.resources

    for resource in resources:
        blueprint = resource.port.entity.mappings.blueprint.strip('"')
        if resource.kind in kinds:
            kinds[resource.kind].append(blueprint)
        elif kind == resource.kind:
            kinds[resource.kind] = [blueprint]

    return kinds
