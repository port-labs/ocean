from enum import StrEnum


class ObjectKind(StrEnum):
    COPILOT_TEAM_METRICS = "copilot-team-metrics"
    COPILOT_ORGANIZATION_METRICS = "copilot-organization-metrics"
    ORGANIZATION_USAGE_METRICS = "organization-usage-metrics"
    USER_USAGE_METRICS = "user-usage-metrics"
