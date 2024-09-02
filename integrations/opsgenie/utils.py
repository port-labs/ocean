from enum import StrEnum


class ObjectKind(StrEnum):
    ALERT = "alert"
    SERVICE = "service"
    TEAM = "team"
    INCIDENT = "incident"
    SCHEDULE = "schedule"


# A dictionary to map each resource type to its API version
RESOURCE_API_VERSIONS = {
    ObjectKind.ALERT: "v2",
    ObjectKind.SERVICE: "v1",
    ObjectKind.TEAM: "v2",
    ObjectKind.INCIDENT: "v1",
    ObjectKind.SCHEDULE: "v2",
}


class ResourceKindsWithSpecialHandling(StrEnum):
    SERVICE = ObjectKind.SERVICE
    ALERT = ObjectKind.ALERT
    INCIDENT = ObjectKind.INCIDENT
    SCHEDULE = ObjectKind.SCHEDULE
