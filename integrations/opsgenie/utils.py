from enum import StrEnum


class ObjectKind(StrEnum):
    ALERTS = "alerts"
    SERVICES = "services"
    TEAMS = "teams"


# A dictionary to map each resource type to its API version
RESOURCE_API_VERSIONS = {
    ObjectKind.ALERTS: "v2",
    ObjectKind.SERVICES: "v1",
    ObjectKind.TEAMS: "v2",
}
