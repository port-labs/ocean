from enum import StrEnum
from datetime import datetime, timedelta
from typing import Any, List, Optional, Union
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic import Field, BaseModel
from typing import Literal


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
    RELEASE = "release"
    FILE = "file"
    USER = "user"


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
        expand: Literal["None", "Fields", "Relations", "Links", "All"] = Field(
            default="All",
            description="Expand options for work items. Allowed values are 'None', 'Fields', 'Relations', 'Links' and 'All'. Default value is 'All'.",
        )

    kind: Literal["work-item"]
    selector: AzureDevopsSelector


class FileSelector(BaseModel):
    """Configuration for file selection in Azure DevOps repositories."""

    path: Union[str, List[str]] = Field(
        default="",
        description="Glob pattern(s) to match files (e.g., '**/*.yaml' or ['**/*.json', '**/*.yaml'])",
    )
    repos: Optional[List[str]] = Field(
        default=None,
        description="List of repository names to scan. If None, scans all repositories.",
    )
    max_depth: Optional[int] = Field(
        default=None,
        description="Maximum directory depth to traverse. If None, no depth limit is applied.",
    )


class AzureDevopsFileSelector(Selector):
    """Selector for Azure DevOps file resources."""

    query: str
    files: FileSelector = Field(
        default_factory=FileSelector,
        description="Configuration for file selection and scanning",
    )


class AzureDevopsFileResourceConfig(ResourceConfig):
    kind: Literal["file"]
    selector: AzureDevopsFileSelector


class TeamSelector(Selector):
    include_members: bool = Field(
        alias="includeMembers",
        default=False,
        description="Whether to include the members of the team, defaults to false",
    )


class AzureDevopsTeamResourceConfig(ResourceConfig):
    kind: Literal["team"]
    selector: TeamSelector


class GitPortAppConfig(PortAppConfig):
    spec_path: List[str] | str = Field(alias="specPath", default="port.yml")
    use_default_branch: bool | None = Field(
        default=None,
        description=(
            "If set to true, it uses default branch of the repository"
            " for syncing the entities to Port. If set to false or None"
            ", it uses the branch mentioned in the `branch` config pro"
            "perty."
        ),
        alias="useDefaultBranch",
    )
    branch: str = "main"
    resources: list[
        AzureDevopsProjectResourceConfig
        | AzureDevopsWorkItemResourceConfig
        | AzureDevopsTeamResourceConfig
        | AzureDevopsFileResourceConfig
        | ResourceConfig
    ] = Field(default_factory=list)


def extract_branch_name_from_ref(ref: str) -> str:
    return "/".join(ref.split("/")[2:])
