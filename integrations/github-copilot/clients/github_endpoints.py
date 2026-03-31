from enum import Enum


class GithubEndpoints(Enum):
    COPILOT_ORGANIZATION_METRICS_28_DAY = (
        "orgs/{org}/copilot/metrics/reports/organization-28-day/latest"
    )
    COPILOT_USERS_USAGE_METRICS_28_DAY = (
        "orgs/{org}/copilot/metrics/reports/users-28-day/latest"
    )
    LIST_ACCESSIBLE_ORGS = "user/orgs"

    # NOTE: Sunset April 2026, see https://github.blog/changelog/2026-01-29-closing-down-notice-of-legacy-copilot-metrics-apis/
    COPILOT_TEAM_METRICS = "orgs/{org}/team/{team}/copilot/metrics"
    COPILOT_ORGANIZATION_METRICS = "orgs/{org}/copilot/metrics"
    LIST_TEAMS = "orgs/{org}/teams"
