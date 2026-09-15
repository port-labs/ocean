from enum import StrEnum


class ObjectKind(StrEnum):
    """Object kinds for Linear integration."""

    TEAM = "team"
    LABEL = "label"
    ISSUE = "issue"
    DOCUMENT = "document"
    USER = "user"
    PROJECT = "project"
    INITIATIVE = "initiative"
    TEAM_MEMBERS = "team-members"
    CYCLE = "cycle"
