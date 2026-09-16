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
    STATE = "state"


class PriorityLabel(StrEnum):
    NO_PRIORITY = "No priority"
    URGENT = "Urgent"
    HIGH = "High"
    NORMAL = "Normal"
    LOW = "Low"


# Linear GraphQL priority is Int 0-4; Port actions use the label.
PRIORITY_BY_LABEL: dict[PriorityLabel, int] = {
    PriorityLabel.NO_PRIORITY: 0,
    PriorityLabel.URGENT: 1,
    PriorityLabel.HIGH: 2,
    PriorityLabel.NORMAL: 3,
    PriorityLabel.LOW: 4,
}
