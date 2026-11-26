from typing import Literal, List

from pydantic.v1 import Field, BaseModel
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    Selector,
    ResourceConfig,
)


class FoldersSelector(BaseModel):
    path: str = Field(
        title="Path",
        description="Relative folder path to export under the repository.",
    )
    repos: List[str] = Field(
        default_factory=list,
        title="Repositories",
        description="Optional list of repository names to limit folder export to.",
    )
    branch: str | None = Field(
        default=None,
        title="Branch",
        description="Branch to use for folder export. Defaults to the repository default branch.",
    )


class GitlabSelector(Selector):
    folders: List[FoldersSelector] = Field(
        default_factory=list,
        title="Folders",
        description="Folders to export as monorepo-style resources.",
    )


class GitlabFolderResourceConfig(ResourceConfig):
    kind: Literal["folder"] = Field(
        title="GitLab Folder",
        description="GitLab folder resource kind for monorepo-style folder export.",
    )
    selector: GitlabSelector


class GitlabGroupResourceConfig(ResourceConfig):
    kind: Literal["group"] = Field(
        title="GitLab Group",
        description="GitLab group resource kind.",
    )


class GitlabIssueResourceConfig(ResourceConfig):
    kind: Literal["issue"] = Field(
        title="GitLab Issue",
        description="GitLab issue resource kind.",
    )


class GitlabJobResourceConfig(ResourceConfig):
    kind: Literal["job"] = Field(
        title="GitLab Job",
        description="GitLab job resource kind.",
    )


class GitlabMergeRequestResourceConfig(ResourceConfig):
    kind: Literal["merge-request"] = Field(
        title="GitLab Merge Request",
        description="GitLab merge request resource kind.",
    )


class GitlabPipelineResourceConfig(ResourceConfig):
    kind: Literal["pipeline"] = Field(
        title="GitLab Pipeline",
        description="GitLab pipeline resource kind.",
    )


class GitlabMemberSelector(Selector):
    include_inherited_members: bool = Field(
        alias="includeInheritedMembers",
        default=False,
        title="Include Inherited Members",
        description="If set to true, the integration will include inherited members in the group members list. Default value is false",
    )
    include_bot_members: bool = Field(
        alias="includeBotMembers",
        default=False,
        title="Include Bot Members",
        description="If set to false, bots will be filtered out from the members list. Default value is true",
    )
    include_verbose_member_object: bool = Field(
        alias="includeVerboseMemberObject",
        default=False,
        title="Include Verbose Member Object",
        description=(
            "If set to true, the integration will include the verbose/entire member object in the members list. Default value is false, "
            "this will reduce the memory footprint of the integration"
        ),
    )


class GitlabGroupWithMembersResourceConfig(ResourceConfig):
    kind: Literal["group-with-members"] = Field(
        title="GitLab Group With Members",
        description="GitLab group resource kind including group members.",
    )
    selector: GitlabMemberSelector


class GitlabProjectWithMembersResourceConfig(ResourceConfig):
    kind: Literal["project-with-members"] = Field(
        title="GitLab Project With Members",
        description="GitLab project resource kind including project members.",
    )
    selector: GitlabMemberSelector


GitlabObjectWithMembersResourceConfig = (
    GitlabGroupWithMembersResourceConfig | GitlabProjectWithMembersResourceConfig
)


class FilesSelector(BaseModel):
    path: str = Field(
        title="Path",
        description="The path to get the files from",
    )
    repos: List[str] = Field(
        default_factory=list,
        title="Repositories",
        description="A list of repositories to search files in",
    )


class GitLabProjectSelector(Selector):
    include_labels: bool = Field(
        alias="includeLabels",
        title="Include Labels",
        description="Whether to enrich projects with labels",
        default=False,
    )


class GitLabFilesSelector(Selector):
    files: FilesSelector = Field(
        title="Files",
        description="File matching configuration for GitLab file resources.",
    )


class GitLabFilesResourceConfig(ResourceConfig):
    selector: GitLabFilesSelector
    kind: Literal["file"] = Field(
        title="GitLab File",
        description="GitLab file resource kind.",
    )


class GitLabProjectResourceConfig(ResourceConfig):
    selector: GitLabProjectSelector
    kind: Literal["project"] = Field(
        title="GitLab Project",
        description="GitLab project resource kind.",
    )


class GitlabPortAppConfig(PortAppConfig):
    spec_path: str | List[str] = Field(
        alias="specPath",
        default="**/port.yml",
        title="Spec Path",
        description="Path glob for Port spec files to sync from GitLab repositories.",
    )
    branch: str | None = Field(
        default=None,
        title="Branch",
        description="Git branch to use when syncing spec files. Defaults to the repository default branch.",
    )
    filter_owned_projects: bool | None = Field(
        alias="filterOwnedProjects",
        default=True,
        title="Filter Owned Projects",
        description="If true, only projects owned by the authenticated user or group are synced.",
    )
    project_visibility_filter: str | None = Field(
        alias="projectVisibilityFilter",
        default=None,
        title="Project Visibility Filter",
        description="Optional GitLab visibility filter for projects (e.g. public, internal, private).",
    )
    resources: list[
        GitlabGroupWithMembersResourceConfig
        | GitlabProjectWithMembersResourceConfig
        | GitLabFilesResourceConfig
        | GitLabProjectResourceConfig
        | GitlabFolderResourceConfig
        | GitlabGroupResourceConfig
        | GitlabIssueResourceConfig
        | GitlabJobResourceConfig
        | GitlabMergeRequestResourceConfig
        | GitlabPipelineResourceConfig
    ] = Field(
        default_factory=list
    )  # type: ignore
