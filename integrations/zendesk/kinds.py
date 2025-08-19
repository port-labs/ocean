from enum import StrEnum


class Kinds(StrEnum):
    TICKET = "ticket"
    USER = "user"
    ORGANIZATION = "organization"
    GROUP = "group"
    BRAND = "brand"