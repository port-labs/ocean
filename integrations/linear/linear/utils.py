from enum import StrEnum


class ObjectKind(StrEnum):
    """Object kinds for Linear integration."""

    TEAM = "team"
    LABEL = "label"
    ISSUE = "issue"
    DOCUMENT = "document"
    USER = "user"
    PROJECT = "project"
    TEAM_MEMBERS = "team-members"
    CYCLE = "cycle"


# Linear GraphQL priority is Int 0-4; Port actions use the label.
PRIORITY_BY_LABEL = {
    "No priority": 0,
    "Urgent": 1,
    "High": 2,
    "Normal": 3,
    "Low": 4,
}
