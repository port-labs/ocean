from enum import StrEnum


class ObjectKind(StrEnum):
    # Organization-scoped kinds
    ORGANIZATION_USAGE_METRICS = "organization-usage-metrics"
    USER_USAGE_METRICS = "user-usage-metrics"
    ORGANIZATION_USER_USAGE_METRICS = "organization-user-usage-metrics"

    # Enterprise-scoped kinds
    ENTERPRISE_USAGE_METRICS = "enterprise-usage-metrics"
    ENTERPRISE_USER_USAGE_METRICS = "enterprise-user-usage-metrics"
