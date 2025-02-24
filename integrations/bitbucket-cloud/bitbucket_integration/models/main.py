from enum import StrEnum


class ObjectKind(StrEnum):
    REPOSITORY = "repository"
    PROJECT = "project"
    PULL_REQUEST = "pull-request"
    COMPONENT = "component"
