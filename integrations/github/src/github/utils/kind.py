from enum import StrEnum


class ObjectKind(StrEnum):
    REPOSITORY = "repository"
    PULL_REQUEST = "pull-request"
    ISSUE = "issue"
    TEAM = "team"
    WORKFLOW = "workflow"
    FOLDER = "folder"
