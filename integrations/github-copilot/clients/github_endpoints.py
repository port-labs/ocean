from enum import Enum


class GithubEndpoints(Enum):
    COPILOT_TEAM_METRICS = "orgs/{org}/team/{team}/copilot/metrics"
    COPILOT_ORGANIZATION_METRICS = "orgs/{org}/copilot/metrics"
    COPILOT_ORGANIZATION_BILLING = "orgs/{org}/copilot/billing"
    COPILOT_ORGANIZATION_SEATS = "orgs/{org}/copilot/billing/seats"
    LIST_ACCESSIBLE_ORGS = "user/orgs"
    LIST_TEAMS = "orgs/{org}/teams"
