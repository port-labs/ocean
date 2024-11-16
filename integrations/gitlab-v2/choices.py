from enum import StrEnum


class RequestType(StrEnum):
    GET = "GET"
    POST = "POST"


class Entity(StrEnum):
    GROUP = "group"
    PROJECT = "project"
    MERGE_REQUEST = "merge-request"
    ISSUE = "issue"


class Endpoint(StrEnum):
    GROUP = "/groups"
    PROJECT = "/projects?membership=yes"
    MERGE_REQUEST = "/merge_requests"
    ISSUE = "/issues"
