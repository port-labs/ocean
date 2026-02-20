from enum import Enum


class GithubEndpoints(Enum):
    COPILOT_ORGANIZATION_METRICS_28_DAY = (
        "orgs/{org}/copilot/metrics/reports/organization-28-day/latest"
    )
    COPILOT_ORGANIZATION_METRICS_1_DAY = (
        "orgs/{org}/copilot/metrics/reports/organization-1-day"
    )
    LIST_ACCESSIBLE_ORGS = "user/orgs"
