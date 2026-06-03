from enum import StrEnum


class Kinds(StrEnum):
    PROJECT = "project"
    ISSUE = "issue"
    USER = "user"
    TEAM = "team"
    RELEASE = "release"
    BOARD = "board"
    SPRINT = "sprint"
    BACKLOG = "backlog"
    EPIC = "epic"
    WORKLOG = "worklog"
