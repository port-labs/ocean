# integrations/github/utils.py
from enum import StrEnum

class ObjectKind(StrEnum):
    REPOSITORY = "githubRepository"
    PULL_REQUEST = "githubPullRequest"
    ISSUE = "githubIssue"
    FILE = "file"
    FOLDER = "githubFolder"