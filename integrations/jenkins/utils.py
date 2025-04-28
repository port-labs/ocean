from enum import StrEnum


class ObjectKind(StrEnum):
    JOB = "job"
    BUILD = "build"
    USER = "user"
    STAGE = "stage"
