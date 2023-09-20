from enum import StrEnum


class ObjectKind(StrEnum):
    ALERT = "alerts"
    SERVICE = "services"
    TEAM = "teams"
    INCIDENT = "incidents"


# A dictionary to map each resource type to its API version
RESOURCE_API_VERSIONS = {
    ObjectKind.ALERT: "v2",
    ObjectKind.SERVICE: "v1",
    ObjectKind.TEAM: "v2",
    ObjectKind.INCIDENT: "v1",
}
