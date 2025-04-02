from enum import Enum

class GithubEndpoints(Enum):
    COPILOT_TEAM_METRICS = "orgs/{org}/team/{team}/copilot/metrics"
    COPILOT_ORGANIZATION_METRICS = "orgs/{org}/copilot/metrics"
    LIST_TOKEN_ORGS = "user/orgs"
    LIST_TEAMS = "orgs/{org}/teams"
