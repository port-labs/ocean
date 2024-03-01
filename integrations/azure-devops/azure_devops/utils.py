from enum import StrEnum

class Kind(StrEnum):
    REPOSITORY = "repository"
    REPOSITORY_POLICY = "repository-policy"
    PULL_REQUEST = "pull-request"
    WORK_ITEM = "work-item"
    PIPELINE = "pipeline"
    BOARD = "board"
    MEMBER = "member"
    TEAM = "team"
    PROJECT = "project"
