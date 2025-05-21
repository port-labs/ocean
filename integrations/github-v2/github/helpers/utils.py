from enum import StrEnum


class GithubClientType(StrEnum):
    REST = "rest"
    GRAPHQL = "graphql"
    WEBHOOK = "webhook"


class ObjectKind(StrEnum):
    REPOSITORY = "repository"
