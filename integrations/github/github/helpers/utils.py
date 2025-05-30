from enum import StrEnum


class GithubClientType(StrEnum):
    REST = "rest"
    GRAPHQL = "graphql"


class ObjectKind(StrEnum):
    REPOSITORY = "repository"
    USER = "user"
    TEAM = "team"
