from enum import StrEnum


class ObjectKind(StrEnum):
    COMPONENT = "component"
    API = "API"
    GROUP = "group"
    USER = "user"
    SYSTEM = "system"
    DOMAIN = "domain"
    RESOURCE = "resource"
