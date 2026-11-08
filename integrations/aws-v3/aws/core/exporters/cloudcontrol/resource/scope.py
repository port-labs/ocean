from aws.core.exporters.cloud_control_scope import CloudControlResourceScope

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
    return parts[1].lower() in CLOUD_CONTROL_GLOBAL_SERVICES


def resolve_cloud_control_is_regional(
    type_name: str,
    resource_scope: CloudControlResourceScope,
) -> bool:
    """Resolve ``auto`` / ``regional`` / ``global`` into whether resync is regional."""
    if resource_scope == CloudControlResourceScope.GLOBAL:
        return False
    if resource_scope == CloudControlResourceScope.REGIONAL:
        return True
    return not is_cloud_control_global_kind(type_name)
