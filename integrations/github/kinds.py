"""
kinds.py
--------
Defines an enumeration for GitHub entity kinds.
"""

from enum import StrEnum

class Kinds(StrEnum):
    REPOSITORY = "repository"
    PULL_REQUEST = "pull-request"
    ISSUE = "issue"
    TEAM = "team"
    WORKFLOW = "workflow"
    FILE = "file"
