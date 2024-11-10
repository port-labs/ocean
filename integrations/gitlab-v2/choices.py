import enum


class Entity(enum.StrEnum):
    GROUP = "group"
    PROJECT = "project"
    MERGE_REQUEST = "merge-request"
    ISSUE = "issue"


class Endpoint(enum.StrEnum):
    GROUP = "/groups"
    PROJECT = "/projects?membership=yes"
    MERGE_REQUEST = "/merge_requests"
    ISSUE = "/issues"
