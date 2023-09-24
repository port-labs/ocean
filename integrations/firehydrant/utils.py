from enum import StrEnum


class ObjectKind(StrEnum):
    ENVIRONMENT = "environment"
    INCIDENT = "incident"
    SERVICE = "service"
    RETROSPECTIVE = "retrospective"


# A dictionary to map each resource type to its API path
RESOURCE_API_PATH_MAPPER = {
    ObjectKind.ENVIRONMENT: "environments",
    ObjectKind.INCIDENT: "incidents",
    ObjectKind.SERVICE: "services",
    ObjectKind.RETROSPECTIVE: "post_mortems/reports",
}
