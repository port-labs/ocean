from enum import StrEnum


class ObjectKind(StrEnum):
    PROJECT = "project"
    FOLDER = "folder"
    REPOSITORY = "repository"
    PULL_REQUEST = "pull-request"
