from enum import StrEnum


class ObjectKind(StrEnum):
    GROUP = "group"
    PROJECT = "project"
    MERGE_REQUEST = "merge_request"
    ISSUE = "issue"
    PUSH = "push"
    TAG_PUSH = "tag_push"
    GROUP_TOKEN = "group_token"
    PROJECT_TOKEN = "project_token"
    PIPELINE = "pipeline"
    JOB = "job"
    RELEASE = "release"


RESOURCE_API_VERSIONS = {
    ObjectKind.GROUP: "v4",
    ObjectKind.PROJECT: "v4",
    ObjectKind.MERGE_REQUEST: "v4",
    ObjectKind.ISSUE: "v4",
}


class ResourceKindsHandledViaWebhooks(StrEnum):
    ISSUE = ObjectKind.ISSUE
    MERGE_REQUEST = ObjectKind.MERGE_REQUEST
    PUSH = ObjectKind.PUSH
    TAG_PUSH = ObjectKind.TAG_PUSH
    PROJECT_TOKEN = ObjectKind.PROJECT_TOKEN
    GROUP_TOKEN = ObjectKind.GROUP_TOKEN
    JOB = ObjectKind.JOB
    PIPELINE = ObjectKind.PIPELINE
    RELEASE = ObjectKind.RELEASE
