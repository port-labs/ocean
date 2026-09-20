from pydantic import BaseModel


class JiraTransitionStatus(BaseModel):
    name: str


class JiraIssueTransition(BaseModel):
    id: str
    to: JiraTransitionStatus


class JiraIssueTransitionsResponse(BaseModel):
    transitions: list[JiraIssueTransition]
