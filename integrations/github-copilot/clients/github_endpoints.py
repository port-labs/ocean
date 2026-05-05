from enum import Enum


class GithubEndpoints(Enum):
    # Organization endpoints
    COPILOT_ORGANIZATION_METRICS_28_DAY = (
        "orgs/{org}/copilot/metrics/reports/organization-28-day/latest"
    )
    COPILOT_USERS_USAGE_METRICS_28_DAY = (
        "orgs/{org}/copilot/metrics/reports/users-28-day/latest"
    )
    LIST_ACCESSIBLE_ORGS = "user/orgs"

    # Enterprise endpoints
    COPILOT_ENTERPRISE_METRICS_28_DAY = (
        "/enterprises/{enterprise}/copilot/metrics/reports/enterprise-28-day/latest"
    )
    COPILOT_ENTERPRISE_USERS_USAGE_METRICS_28_DAY = (
        "/enterprises/{enterprise}/copilot/metrics/reports/users-28-day/latest"
    )
