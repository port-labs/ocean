from enum import StrEnum


class PortGithubResources(StrEnum):
    REPO = "repository"
    ISSUE = "issues"
    TEAM = "team"
    WORKFLOW = "workflows"
    PR = "pull-request"
