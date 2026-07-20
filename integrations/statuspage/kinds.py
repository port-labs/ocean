from enum import StrEnum


class ObjectKind(StrEnum):
    PAGE = "statuspage"
    COMPONENT_GROUPS = "component_group"
    COMPONENT = "component"
    INCIDENT = "incident"
    INCIDENT_UPDATE = "incident_update"
