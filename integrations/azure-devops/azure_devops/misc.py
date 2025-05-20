from datetime import datetime, timedelta
from enum import StrEnum
import fnmatch
from typing import Any, List, Literal, Optional, Union

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic.v1 import Field, BaseModel, validator


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
    paths: Union[str, List[str]], allow_glob: bool = False
) -> Union[str, List[str]]:
    """Shared path validation logic.

    Args:
        paths: Path or list of paths to validate
        allow_glob: Whether to allow glob patterns (*) in paths
    """
    path_list = [paths] if isinstance(paths, str) else paths

    if not path_list:
        raise ValueError("At least one path must be specified")

    valid_paths = []

    for path in path_list:
        # Skip empty paths
        if not path or not path.strip():
            continue

        # Remove leading/trailing slashes and spaces
        normalized_path = path.strip().strip("/")

        # Basic path validation
        if ".." in normalized_path:
            raise ValueError("Path traversal is not allowed")

        # For non-glob paths, validate there are no glob characters
        if not allow_glob and "*" in normalized_path:
            raise ValueError(
                f"Path '{path}' contains glob patterns which are not allowed. "
                "Please provide explicit file paths like 'src/config.yaml' or 'docs/README.md'"
            )

        # For glob paths, only allow * pattern
        if allow_glob and any(
            char in normalized_path for char in {"?", "[", "]", "{", "}", "**"}
        ):
            raise ValueError(
                f"Path '{path}' contains unsupported glob characters. "
                "Only '*' pattern is supported for matching within a path segment."
            )

        valid_paths.append(normalized_path)

    if not valid_paths:
        raise ValueError("No valid paths provided. Please provide valid paths.")

    return valid_paths if isinstance(paths, list) else valid_paths[0]


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
        patterns = [v] if isinstance(v, str) else v

        if not patterns:
            raise ValueError("At least one file path must be specified")

        invalid_chars = {"*", "?", "[", "]", "{", "}", "**"}
        valid_paths = []

        for path in patterns:
            # Skip empty paths
            if not path or not path.strip():
                continue

            # Remove leading/trailing slashes and spaces
            cleaned_path = path.strip().strip("/")

            # Check for invalid glob characters
            if any(char in cleaned_path for char in invalid_chars):
                raise ValueError(
                    f"Path '{path}' contains glob patterns which are not allowed. "
                    "Please provide explicit file paths like 'src/config.yaml' or 'docs/README.md'"
                )

            valid_paths.append(cleaned_path)

        if not valid_paths:
            raise ValueError(
                "No valid file paths provided. Please provide explicit file paths "
                "like 'src/config.yaml' or 'docs/README.md'"
            )

        return valid_paths


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
        Supports glob pattern (*) for matching within a path segment:
        - Use * to match any characters within a path segment

        Examples of valid paths:
        - "src/backend" - Match exact folder
        - "src/*" - Match all immediate folders under src
        - "src/test*" - Match all immediate folders under src starting with 'test'
        - "src/*/docs" - Match docs folder under any immediate folder in src
        - "src/api*/v2" - Match v2 folder under any folder starting with 'api' in src
        - "packages/*/src" - Match src folder under any immediate subfolder of packages
        """,
    )
    repos: list[RepositoryBranchMapping] = Field(
        default_factory=list,
        alias="repos",
        description="Specify the repositories and branches to include under this relative path",
    )

    @validator("path")
    @classmethod
    def validate_folder_path(cls, path: str) -> str:
        """Validate folder paths - only * glob pattern allowed"""
        if not path or not path.strip():
            raise ValueError("Folder path must be specified")

        # Remove leading/trailing slashes and spaces
        normalized_path = path.strip().strip("/")

        # Basic path validation
        if ".." in normalized_path:
            raise ValueError("Path traversal is not allowed")

        # Check for unsupported glob patterns
        if not fnmatch.fnmatch(normalized_path, "*"):
            raise ValueError(
                f"Path '{path}' contains unsupported glob patterns. "
                "Only '*' pattern is supported for matching within a path segment."
            )
        return normalized_path


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
