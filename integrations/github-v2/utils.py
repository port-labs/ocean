from enum import StrEnum


class PortGithubResources(StrEnum):
    REPO = "repository"
    PR = "pull-requests"
    ISSUE = "issues"
    TEAM = "teams"
    WORKFLOW = "workflows"
