from enum import StrEnum


class Kinds(StrEnum):
    ORGANIZATION = "organization"
    PROJECT = "project"
    ISSUE = "issue"
    TARGET = "target"
    VULNERABILITY = "vulnerability"
