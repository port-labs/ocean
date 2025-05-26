from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from port_ocean.core.handlers.port_app_config.models import ResourceConfig, Selector


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
    FOLDER = "folder"


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


def extract_branch_name_from_ref(ref: str) -> str:
    return "/".join(ref.split("/")[2:])


class RepositoryBranchMapping(BaseModel):
    name: str = Field(description="Repository name")
    branch: str | None = Field(default=None, description="Branch to scan")


class FolderPattern(BaseModel):
    path: str = Field(
        default="",
        alias="path",
        description="""Specify the repositories and folders to include under this relative path.
        Supports glob pattern (*) for matching within a path segment:
        - Use * to match any characters within a path segment

        Examples of valid paths:
        - "src/backend" - Matches the exact backend folder inside src
        - "src/*" - Matches all immediate subfolders inside src (e.g., src/api, src/utils)
        - "src/*/docs" - Matches the docs folder inside any immediate subfolder of src (e.g., src/api/docs, src/utils/docs)
        """,
    )
    repos: list[RepositoryBranchMapping] = Field(
        default_factory=list,
        alias="repos",
        description="Specify the repositories and branches to include under this relative path",
    )


class AzureDevopsFolderSelector(Selector):
    """Selector for Azure DevOps folder scanning configuration"""

    project_name: str = Field(
        ...,
        description="Name of the Azure DevOps project that contains the repositories to be scanned",
    )
    folders: list[FolderPattern] = Field(
        default_factory=list,
        alias="folders",
        description="Specify the repositories, branches and folders to include under this relative path",
    )


class AzureDevopsFolderResourceConfig(ResourceConfig):
    """Resource configuration for folder scanning"""

    kind: Literal["folder"]
    selector: AzureDevopsFolderSelector
