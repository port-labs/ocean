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

from gitlab.helpers.utils import GitLabDeploymentStatus, GitlabAccessLevel, ObjectKind
from gitlab.entity_processors.file_entity_processor import FileEntityProcessor
from gitlab.entity_processors.search_entity_processor import SearchEntityProcessor
from datetime import datetime, timedelta, timezone

FILE_PROPERTY_PREFIX = "file://"
SEARCH_PROPERTY_PREFIX = "search://"

ISO_8601_DATETIME_REGEX = (
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})$"
)


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


class PipelineQueryParams(BaseModel):
    """Gitlab API query params that filters returned pipelines"""

    name: str | None = Field(
        default=None,
        title="Name",
        description="Return pipelines with the specified name.",
    )
    scope: Literal["running", "pending", "finished", "branches", "tags"] | None = Field(
        default=None,
        title="Scope",
        description="Limit pipelines to a lifecycle stage (running, pending, finished) or to those triggered for branches or tags.",
    )
    status: (
        Literal[
            "created",
            "waiting_for_resource",
            "preparing",
            "pending",
            "running",
            "success",
            "failed",
            "canceled",
            "skipped",
            "manual",
            "scheduled",
        ]
        | None
    ) = Field(
        default=None,
        title="Status",
        description="Return only pipelines currently in the given execution status.",
    )
    source: (
        Literal[
            "push",
            "schedule",
            "web",
            "merge_request_event",
            "api",
            "chat",
            "external",
            "external_pull_request_event",
            "ondemand_dast_scan",
            "ondemand_dast_validation",
            "parent_pipeline",
            "pipeline",
            "security_orchestration_policy",
            "trigger",
            "webide",
        ]
        | None
    ) = Field(
        default=None,
        title="Source",
        description="Return only pipelines triggered by the given source.",
    )
    ref: str | None = Field(
        default=None,
        title="Ref",
        description="Return only pipelines that ran against the given branch or tag name.",
    )
    sha: str | None = Field(
        default=None,
        title="SHA",
        description="Return only pipelines that ran against the given commit SHA.",
    )
    yaml_errors: bool | None = Field(
        default=None,
        title="YAML Errors",
        description="If true, return only pipelines whose .gitlab-ci.yml configuration is invalid.",
    )
    username: str | None = Field(
        default=None,
        title="Username",
        description="Return only pipelines triggered by the user with this GitLab username.",
    )
    updated_after: str | None = Field(
        default=None,
        title="Updated After",
        description="Return only pipelines updated after this timestamp. Expected in ISO 8601 format (e.g. 2019-03-15T08:00:00Z).",
        regex=ISO_8601_DATETIME_REGEX,
    )
    updated_before: str | None = Field(
        default=None,
        title="Updated Before",
        description="Return only pipelines updated before this timestamp. Expected in ISO 8601 format (e.g. 2019-03-15T08:00:00Z).",
        regex=ISO_8601_DATETIME_REGEX,
    )
    created_after: str | None = Field(
        default=None,
        title="Created After",
        description="Return only pipelines created after this timestamp. Expected in ISO 8601 format (e.g. 2019-03-15T08:00:00Z).",
        regex=ISO_8601_DATETIME_REGEX,
    )
    created_before: str | None = Field(
        default=None,
        title="Created Before",
        description="Return only pipelines created before this timestamp. Expected in ISO 8601 format (e.g. 2019-03-15T08:00:00Z).",
        regex=ISO_8601_DATETIME_REGEX,
    )

    def generate_query_params(self) -> dict[str, Any]:
        return self.dict(exclude_none=True, exclude_unset=True)


class GroupSelector(Selector):
    include_only_active_groups: Optional[bool] = Field(
        default=None,
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
    include_only_active_projects: Optional[bool] = Field(
        default=None,
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
            "Results are stored under __searchQueries[<name>] as a boolean (True if matches found).\n\n"
            "See <a target='_blank' href='https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/git/gitlab-v2/capabilities?method=hosted&step=choose-method#enrich-entities-with-search-queries'>search queries documentation</a> for usage and examples."
        ),
    )
    included_files: list[str] = Field(
        alias="includedFiles",
        title="Included Files",
        default_factory=list,
        description="List of file paths to fetch from the repository and attach to the project data under __includedFiles",
    )


class BranchSelector(Selector):
    include_only_active_projects: Optional[bool] = Field(
        default=None,
        alias="includeOnlyActiveProjects",
        title="Include Only Active Projects",
        description="Only fetch branches from projects with the specified status",
    )
    regex: Optional[str] = Field(
        default=None,
        title="Regex",
        description="Return list of branches with names matching a <a href='https://github.com/google/re2/wiki/Syntax' target='_blank'>re2</a> regular expression. Cannot be used together with search.",
    )
    search: Optional[str] = Field(
        default=None,
        title="Search",
        description="Return list of branches containing the search string. You can use ^term to find branches that begin with term, and term$ to find branches that end with term. If regex is also set, regex takes precedence and this field is ignored.",
    )
    default_branch_only: bool = Field(
        default=True,
        alias="defaultBranchOnly",
        title="Default Branches Only",
        description="Only fetch default branches for each project",
    )


class PipelineSelector(ProjectSelector):
    api_query_params: PipelineQueryParams | None = Field(
        default=None,
        alias="apiQueryParams",
        title="Pipelines Query Params",
        description="Query params for Gitlab's Pipeline's API",
    )


class JobsSelector(ProjectSelector):
    pipeline_query_params: PipelineQueryParams | None = Field(
        default=None,
        alias="pipelineQueryParams",
        title="Pipelines Query Params",
        description="Query params for Gitlab's Pipeline's API",
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
        description="If set to true, the integration will include inherited members in the group members list.",
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


class GitlabProjectMemberSelector(Selector):
    include_only_active_projects: Optional[bool] = Field(
        default=None,
        alias="includeOnlyActiveProjects",
        title="Include Only Active Projects",
        description="Filter projects by active status",
    )
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
        description="If set to true, the integration will include inherited members in the project members list. Default value is false",
    )


class GitlabProjectWithMembersResourceConfig(ResourceConfig):
    kind: Literal["project-with-members"] = Field(
        title="GitLab Project With Members",
        description="GitLab project with members resource kind.",
    )
    selector: GitlabProjectMemberSelector = Field(
        title="Project With Members Selector",
        description="Selector for the GitLab project with members resource.",
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
        description="List of file paths to fetch and attach to the file entity. This selector will add the content of the file to the API response under the `__includedFiles` field.",
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
        description="Filter issues updated within the last N days (e.g. 30 to fetch issues updated in the last 30 days). Note: large values may cause rate limiting.\n\nSee <a target='_blank' href='https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/git/gitlab-v2/examples#issues-configuration-options'>issues configuration options</a> for more details.",
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
    min_access_level: GitlabAccessLevel = Field(
        alias="minAccessLevel",
        default=GitlabAccessLevel.DEVELOPER,
        title="Min Access Level",
        description="Minimum access level required (10=Guest, 20=Reporter, 30=Developer, 40=Maintainer, 50=Owner)",
    )


class PipelineResourceConfig(ResourceConfig):
    kind: Literal["pipeline"] = Field(
        title="GitLab Pipeline",
        description="GitLab pipeline resource kind.",
    )
    selector: PipelineSelector = Field(
        title="Pipeline Selector",
        description="Selector for the GitLab pipeline resource.",
    )


class JobResourceConfig(ResourceConfig):
    kind: Literal["job"] = Field(
        title="GitLab Job",
        description="GitLab job resource kind.",
    )
    selector: JobsSelector = Field(
        title="Job Selector",
        description="Selector for the GitLab job resource.",
    )


class BranchResourceConfig(ResourceConfig):
    kind: Literal["branch"] = Field(
        title="GitLab Branch",
        description="A GitLab branch belonging to a project repository.",
    )
    selector: BranchSelector = Field(
        title="Branch Selector",
        description="Selector for the GitLab branch resource.",
    )


class GitLabDeploymentQueryParams(BaseModel):
    """Shared API query params that filters returned deployments."""

    class Config:
        allow_population_by_field_name = True

    environment: str | None = Field(
        default=None,
        title="Environment",
        description="Return only deployments for the given environment name.",
    )
    status: GitLabDeploymentStatus | None = Field(
        default=None,
        title="Status",
        description=(
            "Filter by deployment status. Omit to include all deployments regardless of status."
        ),
    )
    updated_after: str | None = Field(
        default=None,
        alias="updatedAfter",
        title="Updated After",
        description=(
            "Return deployments updated after this datetime (ISO 8601). "
            "Recommended for incremental resyncs to avoid fetching the full history every cycle."
        ),
    )

    def build_query_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if self.environment:
            params["environment"] = self.environment
        if self.status:
            params["status"] = self.status.value
        if self.updated_after:
            params["updated_after"] = self.updated_after
        return params


class GitLabDeploymentSelector(Selector):
    include_only_active_projects: bool = Field(
        default=True,
        alias="includeOnlyActiveProjects",
        title="Include Only Active Projects",
        description="If true, only include deployments from active projects (non-archived). If false, include deployments from all projects regardless of their active status.",
    )
    query_params: GitLabDeploymentQueryParams | None = Field(
        default=None,
        alias="apiQueryParams",
        title="API Query Params",
        description="Additional query params to filter deployments.",
    )
    finished_after: datetime | None = Field(
        alias="finishedAfter",
        default=None,
        title="Finished After",
        description=(
            "Return deployments whose CI job finished after this datetime (ISO 8601). "
            "Requires apiQueryParams.status to be 'success'."
        ),
    )
    finished_before: datetime | None = Field(
        alias="finishedBefore",
        default=None,
        title="Finished Before",
        description=(
            "Return deployments whose CI job finished before this datetime (ISO 8601). "
            "Requires apiQueryParams.status to be 'success'."
        ),
    )

    @validator("finished_before", always=True)
    def _finished_at_window_requires_success_status(
        cls,
        finished_before: datetime | None,
        values: dict[str, Any],
    ) -> datetime | None:
        uses_finished_at_window = values.get("finished_after") or finished_before
        if not uses_finished_at_window:
            return finished_before
        api_query_params: GitLabDeploymentQueryParams | None = values.get(
            "query_params"
        )
        if (
            api_query_params is None
            or api_query_params.status != GitLabDeploymentStatus.SUCCESS
        ):
            raise ValueError(
                "apiQueryParams.status must be 'success' when finishedAfter or "
                "finishedBefore is set"
            )
        return finished_before

    def build_query_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {}

        if self.query_params:
            params.update(self.query_params.build_query_params())
        if self.finished_after or self.finished_before:
            params["order_by"] = (
                "id"  # default on GitLab API, tracking this explicitly here for clarity
            )
            params["sort"] = (
                "asc"  # default on GitLab API, tracking this for same reason
            )

            if self.finished_after:
                params["finished_after"] = self.finished_after.isoformat()
            if self.finished_before:
                params["finished_before"] = self.finished_before.isoformat()

        return params


class GitLabDeploymentStatusSelector(Selector):
    include_only_active_projects: bool = Field(
        default=True,
        alias="includeOnlyActiveProjects",
        title="Include Only Active Projects",
        description="If true, only include deployment statuses from active projects (non-archived). If false, include deployment statuses from all projects regardless of their active status.",
    )
    query_params: GitLabDeploymentQueryParams | None = Field(
        default=None,
        alias="apiQueryParams",
        title="API Query Params",
        description="Additional query params to filter deployment statuses.",
    )

    def build_query_params(self) -> dict[str, Any]:
        return self.query_params.build_query_params() if self.query_params else {}


class GitLabDeploymentResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.DEPLOYMENT] = Field(
        title="GitLab Deployment",
        description="GitLab deployment resource kind, representing a CI/CD deployment to an environment.",
    )
    selector: GitLabDeploymentSelector = Field(
        title="Deployment Selector",
        description="Selector for the GitLab deployment resource.",
    )


class GitLabDeploymentStatusResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.DEPLOYMENT_STATUS] = Field(
        title="GitLab Deployment Status",
        description=(
            "GitLab deployment status resource kind, representing the current status of a CI/CD deployment."
        ),
    )
    selector: GitLabDeploymentStatusSelector = Field(
        title="Deployment Status Selector",
        description="Selector for the GitLab deployment status resource.",
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
        | GitlabProjectWithMembersResourceConfig
        | GitLabFoldersResourceConfig
        | GitLabFilesResourceConfig
        | GitlabMergeRequestResourceConfig
        | TagResourceConfig
        | ReleaseResourceConfig
        | PipelineResourceConfig
        | JobResourceConfig
        | BranchResourceConfig
        | GitLabDeploymentResourceConfig
        | GitLabDeploymentStatusResourceConfig
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
                f"selector.includedFiles: ['{pattern[len(FILE_PROPERTY_PREFIX) :]}'] "
                f'and mapping: .__includedFiles["{pattern[len(FILE_PROPERTY_PREFIX) :]}"]'
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
