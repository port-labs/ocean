from enum import StrEnum


class ObjectKind(StrEnum):
    PROJECT = "project"
    USER = "user"
    REPOSITORY = "repository"
    ARTIFACT = "artifact"
