from enum import StrEnum

from pydantic import BaseModel


class IssueScope(BaseModel):
    cluster: str


class IssueProps(BaseModel):
    type: str = "availability"
    statuses: list[str] = ["open", "closed"]


class IssueRequestBody(BaseModel):
    scope: IssueScope
    props: IssueProps = IssueProps()

class KomoObjectKind(StrEnum):
    SERVICE = "komodorService"
    HEALTH_MONITOR = "komodorHealthMonitoring"
    RISK_VIOLATION = "komodorRiskViolations"
    AVAILABILITY_ISSUES = "komodorIssues"
