from enum import StrEnum


class AuditTrailAction(StrEnum):
    CREATED = "created"
    DELETED = "deleted"
    MODIFIED = "modified"
    RESOLVED = "resolved"


class AuditTrailEventName(StrEnum):
    ACCESS_MANAGEMENT = "Access Management"
    TEAMS_MANAGEMENT = "Teams Management"
    SLO = "SLO"
    ROLES_MANAGEMENT = "Roles Management"
    USERS_MANAGEMENT = "Users Management"
    MONITOR = "Monitor"


class AuditTrailAssetType(StrEnum):
    USER = "user"
    TEAM = "team"
    SLO = "slo"
    ROLE = "role"
    MONITOR = "monitor"
    RESTRICTION_POLICY = "restriction_policy"


SERVICE_RELATED_EVENTS = frozenset(
    [
        "service_check",
        "query_alert_monitor",
        "metric_slo_alert",
        "monitor_slo_alert",
        "outlier_monitor",
        "event_v2_alert",
    ]
)

SLO_ACTIONS = frozenset(
    [
        AuditTrailAction.CREATED,
        AuditTrailAction.MODIFIED,
        AuditTrailAction.DELETED,
    ]
)

ROLES_ACTIONS = frozenset(
    [
        AuditTrailAction.CREATED,
        AuditTrailAction.DELETED,
        AuditTrailAction.MODIFIED,
    ]
)
