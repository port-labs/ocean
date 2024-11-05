from enum import StrEnum


class ObjectKind(StrEnum):
    GROUP = "group"
    PROJECT = "project"
    MERGE_REQUEST = "merge_request"
    ISSUE = "issue"


# A dictionary to map each resource type to its API version
RESOURCE_API_VERSIONS = {
    ObjectKind.GROUP: "v4",
    ObjectKind.PROJECT: "v4",
    ObjectKind.MERGE_REQUEST: "v4",
    ObjectKind.ISSUE: "v4",
}


class ResourceKindsWithSpecialHandling(StrEnum):
    GROUP = ObjectKind.GROUP
    PROJECT = ObjectKind.PROJECT
    MERGE_REQUEST = ObjectKind.MERGE_REQUEST
    ISSUE = ObjectKind.ISSUE
