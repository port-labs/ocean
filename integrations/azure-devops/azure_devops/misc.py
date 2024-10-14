from enum import StrEnum
from datetime import datetime, timedelta
from typing import Any
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic import Field
from typing import List, Literal


class Kind(StrEnum):
    REPOSITORY = "repository"
    REPOSITORY_POLICY = "repository-policy"
    PULL_REQUEST = "pull-request"
    PIPELINE = "pipeline"
    MEMBER = "member"
    TEAM = "team"
    PROJECT = "project"
    WORK_ITEM = "work-item"
    BOARD = "board"
    COLUMN = "column"


PULL_REQUEST_SEARCH_CRITERIA: list[dict[str, Any]] = [
    {"searchCriteria.status": "active"},
    {
        "searchCriteria.status": "abandoned",
        "searchCriteria.minTime": datetime.now() - timedelta(days=7),
    },
    {
        "searchCriteria.status": "completed",
        "searchCriteria.minTime": datetime.now() - timedelta(days=7),
    },
]


class AzureDevopsProjectResourceConfig(ResourceConfig):
    class AzureDevopsSelector(Selector):
        query: str
        default_team: bool = Field(
            default=False,
            description="If set to true, it ingests default team for each project to Port. This causes latency while syncing the entities to Port.  Default value is false. ",
            alias="defaultTeam",
        )

    kind: Literal["project"]
    selector: AzureDevopsSelector


class AzureDevopsWorkItemResourceConfig(ResourceConfig):
    class AzureDevopsSelector(Selector):
        query: str
        wiql: str | None = Field(
            default=None,
            description="WIQL query to filter work items. If not provided, all work items will be fetched.",
            alias="wiql",
        )

    kind: Literal["work-item"]
    selector: AzureDevopsSelector


class GitPortAppConfig(PortAppConfig):
    spec_path: List[str] | str = Field(alias="specPath", default="port.yml")
    branch: str = "main"
    resources: list[
        AzureDevopsProjectResourceConfig
        | AzureDevopsWorkItemResourceConfig
        | ResourceConfig
    ] = Field(default_factory=list)


def extract_branch_name_from_ref(ref: str) -> str:
    return "/".join(ref.split("/")[2:])
