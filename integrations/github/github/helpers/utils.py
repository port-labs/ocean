from enum import StrEnum


class GithubClientType(StrEnum):
    REST = "rest"
    GRAPHQL = "graphql"


class ObjectKind(StrEnum):
    REPOSITORY = "repository"
    DEPENDABOT_ALERT = "dependabot-alert"
    CODE_SCANNING_ALERT = "code-scanning-alerts"
