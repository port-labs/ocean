from typing import Literal

CloudControlResourceScope = Literal["auto", "regional", "global"]
ResolvedCloudControlResourceScope = Literal["regional", "global"]

CLOUD_CONTROL_GLOBAL_SERVICES: frozenset[str] = frozenset(
    {
        "cloudfront",
        "route53",
        "waf",
        "waf-regional",
        "iam",
        "organizations",
        "s3",
    }
)


def is_cloud_control_global_kind(type_name: str) -> bool:
    """Infer whether a CloudFormation type is a global AWS service.

    Uses the service segment of ``AWS::Service::Resource`` (e.g. ``IAM``).
    """
    parts = type_name.split("::")
    if len(parts) < 2:
        return False
    return parts[1].lower() in CLOUD_CONTROL_GLOBAL_SERVICES


def resolve_cloud_control_resource_scope(
    type_name: str,
    resource_scope: CloudControlResourceScope,
) -> ResolvedCloudControlResourceScope:
    """Resolve ``auto`` / ``regional`` / ``global`` into a concrete scope."""
    if resource_scope == "global":
        return "global"
    if resource_scope == "regional":
        return "regional"
    return "global" if is_cloud_control_global_kind(type_name) else "regional"
