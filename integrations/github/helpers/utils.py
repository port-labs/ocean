from enum import Enum

class ObjectKind(str, Enum):
    REPOSITORY = "repository"
    PULL_REQUEST = "pull-request"
    ISSUE = "issue"
    TEAM = "team"
    WORKFLOW = "workflow"