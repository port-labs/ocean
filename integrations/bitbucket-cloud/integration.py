from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration
from typing import Literal, Optional
from pydantic.v1 import BaseModel, Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)

UserRole = Literal["member", "contributor", "admin", "owner"]


class RepositoryBranchMapping(BaseModel):
    name: str = Field(
        default="",
        alias="name",
        title="Name",
        description="Specify the repository name",
    )
    branch: str = Field(
        default="default",
        alias="branch",
        title="Branch",
        description="Specify the branch to bring the folders from",
    )


class RepositorySelector(Selector):
    user_role: Optional[UserRole] = Field(
        default=None,
        alias="userRole",
        title="User Role",
        description="Filter repositories by authenticated user's role: member, contributor, admin, or owner",
    )
    repo_query: Optional[str] = Field(
        default=None,
        alias="repoQuery",
        title="Repository Query",
        description='Query string to narrow repositories as per Bitbucket filtering (e.g., name="my-repo")',
    )
    included_files: list[str] = Field(
        alias="includedFiles",
        default_factory=list,
        title="Attached Files",
        description=(
            "List of file paths to fetch from the repository and attach to "
            "the raw data under __includedFiles. E.g. ['README.md', 'CODEOWNERS']"
        ),
    )


class PullRequestSelector(RepositorySelector):
    pull_request_query: str = Field(
        default='state="OPEN"',
        alias="pullRequestQuery",
        title="Pull Request Query",
        description='Query string to narrow pull requests as per Bitbucket filtering (e.g., state="OPEN")',
    )


class FolderPattern(BaseModel):
    path: str = Field(
        default="",
        alias="path",
        description="Specify the repositories and folders to include under this relative path",
        title="Folder Sync Patterns",
    )
    repos: list[RepositoryBranchMapping] = Field(
        default_factory=list,
        alias="repos",
        description="Specify the repositories and branches to include under this relative path",
        title="Specific Repositories",
    )


class BitbucketFolderSelector(RepositorySelector):
    folders: list[FolderPattern] = Field(
        alias="folders",
        title="Folders",
        description="Specify the repositories, branches and folders to include under this relative path",
    )


class BitbucketFolderResourceConfig(ResourceConfig):
    kind: Literal["folder"] = Field(
        title="Bitbucket Folder",
        description="A folder within a Bitbucket repository, scoped to specific branches and paths",
    )
    selector: BitbucketFolderSelector = Field(
        title="Folder Selector",
        description="Selector to filter and configure which Bitbucket folders are synced",
    )


class BitbucketFilePattern(BaseModel):
    path: str = Field(
        default="*/",
        alias="path",
        description="Specify the path to match files from",
        title="File sync patterns",
    )
    repos: list[str] = Field(
        default_factory=list,
        alias="repos",
        description="Specify the repositories to fetch files from",
        title="Specific Repositories",
    )
    skip_parsing: bool = Field(
        default=False,
        alias="skipParsing",
        title="Skip Parsing",
        description="Skip parsing the files and just return the raw file content",
    )
    filenames: list[str] = Field(
        default_factory=list,
        alias="filenames",
        title="File Names",
        description="List of filenames or patterns to search for within the specified path (e.g. ['config.yml', '*.yaml']). Required — if empty, no file search will be performed",
    )


class BitbucketFileSelector(Selector):
    files: BitbucketFilePattern = Field(
        title="File Patterns",
        description="Define which files to sync by specifying path patterns, target repositories, and filenames to match",
    )
    included_files: list[str] = Field(
        title="Additional files",
        alias="includedFiles",
        default_factory=list,
        description="List of file paths to fetch and attach to the file entity. This selector will add the content of the file to the API response under the `__includedFiles` field.",
    )


class BitbucketFileResourceConfig(ResourceConfig):
    kind: Literal["file"] = Field(
        title="Bitbucket File",
        description="A file within a Bitbucket repository, matched by path and filename patterns",
    )
    selector: BitbucketFileSelector = Field(
        title="File Selector",
        description="Selector to filter and configure which Bitbucket files are synced",
    )


class RepositoryResourceConfig(ResourceConfig):
    kind: Literal["repository"] = Field(
        title="Bitbucket Repository",
        description="A Bitbucket repository synced from your workspace",
    )
    selector: RepositorySelector = Field(
        title="Repository Selector",
        description="Selector to filter and configure which Bitbucket repositories are synced",
    )


class PullRequestResourceConfig(ResourceConfig):
    kind: Literal["pull-request"] = Field(
        title="Bitbucket Pull Request",
        description="A pull request in a Bitbucket repository",
    )
    selector: PullRequestSelector = Field(
        title="Pull Request Selector",
        description="Selector to filter and configure which Bitbucket pull requests are synced",
    )


class ProjectResourceConfig(ResourceConfig):
    kind: Literal["project"] = Field(
        title="Bitbucket Project",
        description="A Bitbucket project that groups repositories within a workspace",
    )


class BitbucketAppConfig(PortAppConfig):
    resources: list[
        BitbucketFolderResourceConfig
        | BitbucketFileResourceConfig
        | PullRequestResourceConfig
        | RepositoryResourceConfig
        | ProjectResourceConfig
    ] = Field(
        default_factory=list,
        alias="resources",
        description="Specify the resources to include in the sync",
    )  # type: ignore[assignment]


class BitbucketIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = BitbucketAppConfig
