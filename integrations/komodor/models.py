from enum import StrEnum

from pydantic import BaseModel


class IssueScope(BaseModel):
    cluster: str


class IssueProps(BaseModel):
    type: str = "availability"
    statuses: list[str] = ["open", "closed"]


class IssueBody(BaseModel):
    scope: IssueScope
    props: IssueProps = IssueProps()

class KomoObjectKind(StrEnum):
    SERVICE = "komodorService"
    RISK_VIOLATION = "komodorRiskViolations"
    AVAILABILITY_ISSUES = "komodorIssues"
