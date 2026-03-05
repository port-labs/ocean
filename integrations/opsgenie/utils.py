from enum import StrEnum


class ObjectKind(StrEnum):
    ALERT = "alert"
    SERVICE = "service"
    TEAM = "team"
    INCIDENT = "incident"
    SCHEDULE = "schedule"
    SCHEDULE_ONCALL = "schedule-oncall"
    USER = "user"
    ALERT_POLICY = "policies/alert"
    NOTIFICATION_POLICY = "policies/notification"


# A dictionary to map each resource type to its API version
RESOURCE_API_VERSIONS = {
    ObjectKind.ALERT: "v2",
    ObjectKind.SERVICE: "v1",
    ObjectKind.TEAM: "v2",
    ObjectKind.INCIDENT: "v1",
    ObjectKind.SCHEDULE: "v2",
    ObjectKind.ALERT_POLICY: "v2",
    ObjectKind.NOTIFICATION_POLICY: "v2",
}


class ResourceKindsWithSpecialHandling(StrEnum):
    SERVICE = ObjectKind.SERVICE
    ALERT = ObjectKind.ALERT
    INCIDENT = ObjectKind.INCIDENT
    SCHEDULE = ObjectKind.SCHEDULE
    SCHEDULE_ONCALL = ObjectKind.SCHEDULE_ONCALL
    TEAM = ObjectKind.TEAM
    ALERT_POLICY = ObjectKind.ALERT_POLICY
    NOTIFICATION_POLICY = ObjectKind.NOTIFICATION_POLICY
