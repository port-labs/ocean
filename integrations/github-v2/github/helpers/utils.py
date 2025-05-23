from enum import StrEnum


class GithubClientType(StrEnum):
    REST = "rest"
    GRAPHQL = "graphql"
    WEBHOOK = "webhook"


class ObjectKind(StrEnum):
    """Enum for GitHub resource kinds."""
    REPOSITORY = "repository"
    ENVIRONMENT = "environment"
    DEPLOYMENT = "deployment"
