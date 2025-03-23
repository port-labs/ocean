from pydantic import BaseModel


class IssueScope(BaseModel):
    cluster: str


class IssueProps(BaseModel):
    type: str = "availability"
    statuses: list[str] = ["open", "closed"]


class IssueBody(BaseModel):
    scope: IssueScope
    props: IssueProps = IssueProps()
