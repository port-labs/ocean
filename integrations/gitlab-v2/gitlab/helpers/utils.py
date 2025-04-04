from enum import StrEnum


class ObjectKind(StrEnum):
    PROJECT = "project"
    GROUP = "group"
    ISSUE = "issue"
    MERGE_REQUEST = "merge-request"
    FILE = "file"
