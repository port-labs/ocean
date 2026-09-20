from typing import TypedDict


class JiraTransitionStatus(TypedDict):
    name: str


class JiraIssueTransition(TypedDict):
    id: str
    to: JiraTransitionStatus


class JiraIssueTransitionsResponse(TypedDict):
    transitions: list[JiraIssueTransition]
