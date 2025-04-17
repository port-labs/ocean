from enum import StrEnum

from port_ocean.context.ocean import ocean

from client import GitHub


def create_github_client() -> GitHub:
    github = GitHub(ocean.integration_config.get("github_token"))
    return github


class ObjectKind(StrEnum):
    REPO = "repository"
    PR = "pull-requests"
    ISSUE = "issues"
    TEAM = "teams"
    WORKFLOW = "workflows"
