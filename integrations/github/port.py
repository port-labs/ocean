from enum import StrEnum


class PortGithubResources(StrEnum):
    REPO = "repository"
    PR = "pull-request"
    ISSUE = "issues"
    TEAM = "team"
    WORKFLOW = "workflows"
