from enum import StrEnum
from datetime import datetime, timedelta
from typing import Any


class Kind(StrEnum):
    REPOSITORY = "repository"
    REPOSITORY_POLICY = "repository-policy"
    PULL_REQUEST = "pull-request"
    PIPELINE = "pipeline"
    MEMBER = "member"
    TEAM = "team"
    PROJECT = "project"


PULL_REQUEST_SEARCH_CRITERIA: list[dict[str, Any]] = [
    {"searchCriteria.status": "active"},
    {
        "searchCriteria.status": "all",
        "searchCriteria.maxTime": datetime.now() - timedelta(days=30),
    },
]
