from enum import StrEnum


class Kinds(StrEnum):
    PROJECT = "project"
    ISSUE = "issue"
    USER = "user"
    TEAM = "team"
    # Jira Service Management kinds for incident management
    SERVICE = "service"
    INCIDENT = "incident"
    REQUEST = "request"
    ASSET = "asset"
    SCHEDULE = "schedule"
