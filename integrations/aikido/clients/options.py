from typing import Literal, Optional, TypedDict

from pydantic import BaseModel

from clients.literals import IssueStatusLiteral, IssueTypeLiteral


class ListRepositoriesOptions(TypedDict):
    include_inactive: bool


class ListContainersOptions(TypedDict):
    filter_status: Literal["all", "active", "inactive"]


class IssuesOptions(BaseModel):
    filter_status: Optional[IssueStatusLiteral] = None
    filter_severities: Optional[str] = None  # comma-joined list e.g. "critical,high"
    filter_issue_type: Optional[IssueTypeLiteral] = None
