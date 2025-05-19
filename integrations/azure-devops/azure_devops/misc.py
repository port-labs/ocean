from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, List, Literal, Optional, Union

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic import Field, BaseModel, validator


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


def _validate_path(
    v: Union[str, List[str]], allow_glob: bool = False
) -> Union[str, List[str]]:
    """Shared path validation logic.

    Args:
        v: Path or list of paths to validate
        allow_glob: Whether to allow glob patterns (* and **) in paths
    """
    patterns = [v] if isinstance(v, str) else v

    if not patterns:
        raise ValueError("At least one path must be specified")

    valid_paths = []

    for path in patterns:
        # Skip empty paths
        if not path or not path.strip():
            continue

        # Remove leading/trailing slashes and spaces
        cleaned_path = path.strip().strip("/")

        # Basic path validation
        if ".." in cleaned_path:
            raise ValueError("Path traversal is not allowed")

        # For non-glob paths, validate there are no glob characters
        if not allow_glob and any(
            char in cleaned_path for char in {"*", "?", "[", "]", "{", "}", "**"}
        ):
            raise ValueError(
                f"Path '{path}' contains glob patterns which are not allowed. "
                "Please provide explicit file paths like 'src/config.yaml' or 'docs/README.md'"
            )

        # For glob paths, only allow * and ** patterns
        if allow_glob and any(
            char in cleaned_path for char in {"?", "[", "]", "{", "}"}
        ):
            raise ValueError(
                f"Path '{path}' contains unsupported glob characters. "
                "Only '*' and '**' patterns are supported."
            )

        valid_paths.append(cleaned_path)

    if not valid_paths:
        raise ValueError("No valid paths provided. Please provide valid paths.")

    return valid_paths if isinstance(v, list) else valid_paths[0]


class FileSelector(BaseModel):
    """Configuration for file selection in Azure DevOps repositories."""

    path: Union[str, List[str]] = Field(
        ...,  # Make path required
        description="""
        Explicit file path(s) to fetch. Can be a single path or list of paths.

        Examples of valid paths:
        - "src/config.yaml"
        - "deployment/helm/values.yaml"
        - "config/settings.json"
        - ".github/workflows/ci.yml"
        - "docs/README.md"
        - "src/main.py"
        - "images/logo.png"

        Invalid paths:
        - "*" : glob patterns not allowed
        - "*.yaml" : glob patterns not allowed
        - "src/*.js" : glob patterns not allowed
        - "config/**/*.yaml" : glob patterns not allowed
        - "**/*" : glob patterns not allowed
        - "**" : glob patterns not allowed

        Each path must be an explicit file path relative to the repository root.
        Glob patterns are not supported to prevent overly broad file fetching.
        """,
    )
    repos: Optional[List[str]] = Field(
        default=None,
        description="List of repository names to scan. If None, scans all repositories.",
    )

    @validator("path", allow_reuse=True)
    @classmethod
    def validate_path_patterns(cls, v: Union[str, List[str]]) -> Union[str, List[str]]:
        """Validate file paths - no glob patterns allowed"""
        return _validate_path(v, allow_glob=False)


class AzureDevopsFileSelector(Selector):
    """Selector for Azure DevOps file resources."""

    files: FileSelector = Field(
        description="""Configuration for file selection and scanning.

        Specify explicit file paths to fetch from repositories.
        Example:
        ```yaml
        selector:
          files:
            path:
              - "port.yml"
              - "config/settings.json"
              - ".github/workflows/ci.yml"
            repos:  # optional, if not specified will scan all repositories
              - "my-repo-1"
              - "my-repo-2"
        ```
        """,
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


def extract_branch_name_from_ref(ref: str) -> str:
    return "/".join(ref.split("/")[2:])


class RepositoryBranchMapping(BaseModel):
    name: str = Field(description="Repository name")
    branch: str = Field(default="main", description="Branch to scan")


class FolderPattern(BaseModel):
    path: str = Field(
        default="",
        alias="path",
        description="""Specify the repositories and folders to include under this relative path.
        Supports glob patterns (* and **) for matching multiple folders:
        - Use * to match any characters within a path segment
        - Use ** to match zero or more path segments

        Examples:
        - "src/backend": Match exact folder
        - "src/*": Match all folders under src
        - "src/**/tests": Match all 'tests' folders under 'src' at any depth
        - "**/docs": Match all 'docs' folders at any depth
        """,
    )
    repos: list[RepositoryBranchMapping] = Field(
        default_factory=list,
        alias="repos",
        description="Specify the repositories and branches to include under this relative path",
    )

    @validator("path")
    @classmethod
    def validate_folder_path(cls, v: str) -> Union[str, List[str]]:
        """Validate folder paths - glob patterns (* and **) allowed"""
        return _validate_path(v, allow_glob=True)


class AzureDevopsFolderSelector(Selector):
    """Selector for Azure DevOps folder scanning configuration"""

    folders: list[FolderPattern] = Field(
        default_factory=list,
        alias="folders",
        description="Specify the repositories, branches and folders to include under this relative path",
    )


class AzureDevopsFolderResourceConfig(ResourceConfig):
    """Resource configuration for folder scanning"""

    kind: Literal["folder"]
    selector: AzureDevopsFolderSelector


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
        | AzureDevopsFolderResourceConfig
        | AzureDevopsWorkItemResourceConfig
        | AzureDevopsTeamResourceConfig
        | AzureDevopsFileResourceConfig
        | ResourceConfig
    ] = Field(default_factory=list)
