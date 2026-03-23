from typing import Literal, Any, Type, List, Optional
from loguru import logger
from pydantic import BaseModel, Field, validator

from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers import APIPortAppConfig, JQEntityProcessor
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.webhook.processor_manager import (
    LiveEventsProcessorManager,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from port_ocean.utils.signal import signal_handler

from gitlab.entity_processors.file_entity_processor import FileEntityProcessor
from gitlab.entity_processors.search_entity_processor import SearchEntityProcessor
from datetime import datetime, timedelta, timezone

FILE_PROPERTY_PREFIX = "file://"
SEARCH_PROPERTY_PREFIX = "search://"


class SearchQuery(BaseModel):
    """A search query to execute against a GitLab project during enrichment."""

    name: str = Field(
        description="A unique name for this search query, used as the key in __searchQueries",
    )
    scope: str = Field(
        default="blobs",
        description="The GitLab search scope (e.g. blobs, commits, wiki_blobs, etc.)",
    )
    query: str = Field(
        description="The search query string (e.g. filename:port.yml)",
    )


class GroupSelector(Selector):
    include_only_active_groups: bool = Field(
        default=False,
        alias="includeOnlyActiveGroups",
        title="Include Only Active Groups",
        description="Filter groups by active status",
    )


class ProjectSelector(Selector):
    include_languages: bool = Field(
        alias="includeLanguages",
        title="Include Languages",
        default=False,
        description="Whether to include the languages of the project, defaults to false",
    )
    include_only_active_projects: bool = Field(
        default=False,
        alias="includeOnlyActiveProjects",
        title="Include Only Active Projects",
        description="Filter projects by active status",
    )
    search_queries: list[SearchQuery] = Field(
        alias="searchQueries",
        default_factory=list,
        title="Search Queries",
        description=(
            "List of search queries to execute against each project during enrichment. "
            "Results are stored under __searchQueries[<name>] as a boolean (True if matches found)."
        ),
    )
    included_files: list[str] = Field(
        alias="includedFiles",
        title="Included Files",
        default_factory=list,
        description="List of file paths to fetch from the repository and attach to the project data under __includedFiles",
    )


class ProjectResourceConfig(ResourceConfig):
    kind: Literal["project"] = Field(
        title="GitLab Project",
        description="GitLab project resource kind.",
    )
    selector: ProjectSelector = Field(
        title="Project Selector",
        description="Selector for the GitLab project resource.",
    )


class GroupResourceConfig(ResourceConfig):
    kind: Literal["group"] = Field(
        title="GitLab Group",
        description="GitLab group resource kind.",
    )
    selector: GroupSelector = Field(
        title="Group Selector",
        description="Selector for the GitLab group resource.",
    )


class GitlabMemberSelector(GroupSelector):
    include_bot_members: bool = Field(
        alias="includeBotMembers",
        title="Include Bot Members",
        default=False,
        description="If set to false, bots will be filtered out from the members list. Default value is false",
    )
    include_inherited_members: bool = Field(
        alias="includeInheritedMembers",
        title="Include Inherited Members",
        default=False,
        description="If set to true, the integration will include inherited members in the group members list. Default value is false",
    )


class GitlabGroupWithMembersResourceConfig(ResourceConfig):
    kind: Literal["group-with-members"] = Field(
        title="GitLab Group With Members",
        description="GitLab group with members resource kind.",
    )
    selector: GitlabMemberSelector = Field(
        title="Group With Members Selector",
        description="Selector for the GitLab group with members resource.",
    )


class GitlabMemberResourceConfig(ResourceConfig):
    kind: Literal["member"] = Field(
        title="GitLab Member",
        description="GitLab member resource kind.",
    )
    selector: GitlabMemberSelector = Field(
        title="Member Selector",
        description="Selector for the GitLab member resource.",
    )


class FilesSelector(BaseModel):
    path: str = Field(
        alias="path",
        title="Path",
        description="Specify the path to match files from",
    )
    repos: list[str] = Field(
        description="A list of repositories to search files in",
        default_factory=list,
        title="Repositories",
    )
    skip_parsing: bool = Field(
        default=False,
        alias="skipParsing",
        description="Skip parsing the files and just return the raw file content",
        title="Skip Parsing",
    )


class GitLabFilesSelector(GroupSelector):
    files: FilesSelector
    included_files: list[str] = Field(
        alias="includedFiles",
        title="Included Files",
        default_factory=list,
        description="List of file paths to fetch and attach to the file entity",
    )


class GitLabFilesResourceConfig(ResourceConfig):
    kind: Literal["file"] = Field(
        title="GitLab File",
        description="GitLab file resource kind.",
    )
    selector: GitLabFilesSelector = Field(
        title="File Selector",
        description="Selector for the GitLab file resource.",
    )


class RepositoryBranchMapping(BaseModel):
    name: str = Field(
        alias="name",
        title="Repository Name",
        description="Specify the repository name",
    )
    branch: str = Field(
        default="main",
        alias="branch",
        title="Branch",
        description="Specify the branch to bring the folders from",
    )


class FolderPattern(BaseModel):
    path: str = Field(
        alias="path",
        title="Path",
        description="Specify the repositories and folders to include under this relative path",
    )
    repos: list[RepositoryBranchMapping] = Field(
        default_factory=list,
        alias="repos",
        title="Repositories",
        description="Specify the repositories and branches to include under this relative path",
    )


class GitlabFolderSelector(ProjectSelector):
    folders: list[FolderPattern] = Field(
        default_factory=list,
        alias="folders",
        title="Folders",
        description="Specify the repositories, branches and folders to include under this relative path",
    )


class GitlabMergeRequestSelector(GroupSelector):
    states: List[Literal["opened", "closed", "merged"]] = Field(
        alias="states",
        title="States",
        description="Specify the state of the merge request to match. Allowed values: opened, closed, merged",
        default=["opened"],
    )
    updated_after: float = Field(
        alias="updatedAfter",
        title="Updated After (Days)",
        description=(
            "Specify the number of days to look back for merge requests (e.g. 90 for last 90 days)."
            " Note: large values may cause rate limiting."
        ),
        default=90,
    )

    @property
    def updated_after_datetime(self) -> datetime:
        """Convert the created_after days to a timezone-aware datetime object."""
        return datetime.now(timezone.utc) - timedelta(days=self.updated_after)


class GitlabMergeRequestResourceConfig(ResourceConfig):
    kind: Literal["merge-request"] = Field(
        title="GitLab Merge Request",
        description="GitLab merge request resource kind.",
    )
    selector: GitlabMergeRequestSelector = Field(
        title="Merge Request Selector",
        description="Selector for the GitLab merge request resource.",
    )


class TagResourceConfig(ResourceConfig):
    kind: Literal["tag"] = Field(
        title="GitLab Tag",
        description="GitLab tag resource kind.",
    )
    selector: ProjectSelector = Field(
        title="Tag Selector",
        description="Selector for the GitLab tag resource.",
    )


class ReleaseResourceConfig(ResourceConfig):
    kind: Literal["release"] = Field(
        title="GitLab Release",
        description="GitLab release resource kind.",
    )
    selector: ProjectSelector = Field(
        title="Release Selector",
        description="Selector for the GitLab release resource.",
    )


class GitLabFoldersResourceConfig(ResourceConfig):
    kind: Literal["folder"] = Field(
        title="GitLab Folder",
        description="GitLab folder resource kind.",
    )
    selector: GitlabFolderSelector = Field(
        title="Folder Selector",
        description="Selector for the GitLab folder resource.",
    )


class IssueSelector(GroupSelector):
    issue_type: Optional[Literal["issue", "incident", "test_case", "task"]] = Field(
        default=None,
        alias="issueType",
        title="Issue Type",
        description="Filter issues by type",
    )
    labels: Optional[str] = Field(
        default=None,
        alias="labels",
        title="Labels",
        description="Filter issues by labels",
    )
    non_archived: bool = Field(
        default=True,
        alias="nonArchived",
        title="Non Archived",
        description="Return issues from non archived projects. Default value is true",
    )
    state: Optional[Literal["opened", "closed"]] = Field(
        default=None,
        alias="state",
        title="State",
        description="Filter issues by state",
    )
    updated_after: Optional[float] = Field(
        default=None,
        alias="updatedAfter",
        title="Updated After (Days)",
        description="Filter issues updated on or after the given time in days. Note: large values may cause rate limiting.",
    )

    @property
    def updated_after_datetime(self) -> str:
        """Convert the created_after days to a timezone-aware datetime object in ISO 8601 format"""
        if not self.updated_after:
            return datetime.now(timezone.utc).isoformat()
        return (
            datetime.now(timezone.utc) - timedelta(days=self.updated_after)
        ).isoformat()


class GitlabIssueResourceConfig(ResourceConfig):
    kind: Literal["issue"] = Field(
        title="GitLab Issue",
        description="GitLab issue resource kind.",
    )
    selector: IssueSelector = Field(
        title="Issue Selector",
        description="Selector for the GitLab issue resource.",
    )


class GitlabVisibilityConfig(BaseModel):
    use_min_access_level: bool = Field(
        alias="useMinAccessLevel",
        default=True,
        title="Use Min Access Level",
        description="If true, apply min_access_level filtering. If false, include all accessible resources without filtering",
    )
    min_access_level: Literal[10, 20, 30, 40, 50] = Field(
        alias="minAccessLevel",
        default=30,
        title="Min Access Level",
        description="Minimum access level required (10=Guest, 20=Reporter, 30=Developer, 40=Maintainer, 50=Owner)",
    )

    @validator("min_access_level")
    def validate_access_level(cls, value: int) -> int:
        """Validate that min_access_level is a valid GitLab access level."""
        valid_levels = [
            10,
            20,
            30,
            40,
            50,
        ]  # Guest, Reporter, Developer, Maintainer, Owner
        if value not in valid_levels:
            raise ValueError(
                f"min_access_level must be one of: {valid_levels} (10=Guest, 20=Reporter, 30=Developer, 40=Maintainer, 50=Owner)"
            )
        return value


class PipelineResourceConfig(ResourceConfig):
    kind: Literal["pipeline"] = Field(
        title="GitLab Pipeline",
        description="GitLab pipeline resource kind.",
    )
    selector: ProjectSelector = Field(
        title="Pipeline Selector",
        description="Selector for the GitLab pipeline resource.",
    )


class JobResourceConfig(ResourceConfig):
    kind: Literal["job"] = Field(
        title="GitLab Job",
        description="GitLab job resource kind.",
    )
    selector: ProjectSelector = Field(
        title="Job Selector",
        description="Selector for the GitLab job resource.",
    )


class GitlabPortAppConfig(PortAppConfig):
    visibility: GitlabVisibilityConfig = Field(
        default_factory=GitlabVisibilityConfig,
        alias="visibility",
        title="Visibility",
        description="Configuration for resource visibility and access control",
    )
    resources: list[
        ProjectResourceConfig
        | GroupResourceConfig
        | GitlabIssueResourceConfig
        | GitlabGroupWithMembersResourceConfig
        | GitlabMemberResourceConfig
        | GitLabFoldersResourceConfig
        | GitLabFilesResourceConfig
        | GitlabMergeRequestResourceConfig
        | TagResourceConfig
        | ReleaseResourceConfig
        | PipelineResourceConfig
        | JobResourceConfig
    ] = Field(
        default_factory=list,
        title="Resources",
        description="The list of resource configurations to sync from GitLab.",
    )  # type: ignore[assignment]


class GitManipulationHandler(JQEntityProcessor):
    async def _search(
        self, data: dict[str, Any], pattern: str, field: str | None = None
    ) -> Any:
        entity_processor: Type[JQEntityProcessor]

        if pattern.startswith(FILE_PROPERTY_PREFIX):
            logger.warning(
                f"DEPRECATION: Using 'file://' prefix in mappings is deprecated and will be removed in a future version. "
                f"Pattern: '{pattern}'. "
                f"Use the 'includedFiles' selector instead. Example: "
                f"selector.includedFiles: ['{pattern[len(FILE_PROPERTY_PREFIX):]}'] "
                f'and mapping: .__includedFiles["{pattern[len(FILE_PROPERTY_PREFIX):]}"]'
            )
            entity_processor = FileEntityProcessor
        elif pattern.startswith(SEARCH_PROPERTY_PREFIX):
            logger.warning(
                f"DEPRECATION: Using 'search://' prefix in mappings is deprecated and will be removed in a future version. "
                f"Pattern: '{pattern}'. "
                f"Use the 'searchQueries' selector instead. Example: "
                f"selector.searchQueries: [{{name: '<queryName>', scope: '<scope>', query: '<query>'}}] "
                f'Then map to .__searchQueries["<queryName>"]'
            )
            entity_processor = SearchEntityProcessor
        else:
            entity_processor = JQEntityProcessor

        return await entity_processor(self.context)._search(data, pattern, field)


class GitlabHandlerMixin(HandlerMixin):
    EntityProcessorClass = GitManipulationHandler


class GitlabLiveEventsProcessorManager(LiveEventsProcessorManager, GitlabHandlerMixin):
    pass


class GitlabIntegration(BaseIntegration):
    EntityProcessorClass = GitManipulationHandler

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GitlabPortAppConfig

    def __init__(self, context: PortOceanContext):
        super().__init__(context)

        # Replace default webhook manager with GitLab-specific one
        self.context.app.webhook_manager = GitlabLiveEventsProcessorManager(
            self.context.app.integration_router,
            signal_handler,
            self.context.config.max_event_processing_seconds,
            self.context.config.max_wait_seconds_before_shutdown,
        )
