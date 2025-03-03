from enum import StrEnum


class IntegrationKind(StrEnum):
    ORGANIZATION = "organization"
    PROJECT = "project"
    ISSUE = "issue"
    TARGET = "target"
    VULNERABILITY = "vulnerability"
