from typing import Literal, Any, Type, List
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


class GitlabAccessConfig(BaseModel):
    """Configuration for GitLab access level filtering."""

    use_min_access_level: bool = Field(
        default=True,
        alias="useMinAccessLevel",
        description="Whether to apply min_access_level filtering. Set to false for admin tokens to see all resources.",
    )
    min_access_level: int = Field(
        default=30,  # Developer level
        alias="minAccessLevel",
        description="Minimum access level for syncing (10=Guest, 20=Reporter, 30=Developer, 40=Maintainer, 50=Owner)",
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


class ProjectSelector(Selector):
    include_languages: bool = Field(
        alias="includeLanguages",
        default=False,
        description="Whether to include the languages of the project, defaults to false",
    )


class ProjectResourceConfig(ResourceConfig):
    kind: Literal["project"]
    selector: ProjectSelector


class GitlabMemberSelector(Selector):
    include_bot_members: bool = Field(
        alias="includeBotMembers",
        default=False,
        description="If set to false, bots will be filtered out from the members list. Default value is false",
    )


class GitlabGroupWithMembersResourceConfig(ResourceConfig):
    kind: Literal["group-with-members"]
    selector: GitlabMemberSelector


class GitlabMemberResourceConfig(ResourceConfig):
    kind: Literal["member"]
    selector: GitlabMemberSelector


class FilesSelector(BaseModel):
    path: str = Field(
        alias="path",
        description="Specify the path to match files from",
    )
    repos: list[str] = Field(
        description="A list of repositories to search files in", default_factory=list
    )
    skip_parsing: bool = Field(
        default=False,
        alias="skipParsing",
        description="Skip parsing the files and just return the raw file content",
    )


class GitLabFilesSelector(Selector):
    files: FilesSelector


class GitLabFilesResourceConfig(ResourceConfig):
    selector: GitLabFilesSelector
    kind: Literal["file"]


class RepositoryBranchMapping(BaseModel):
    name: str = Field(
        default="",
        alias="name",
        description="Specify the repository name",
    )
    branch: str = Field(
        default="main",
        alias="branch",
        description="Specify the branch to bring the folders from",
    )


class FolderPattern(BaseModel):
    path: str = Field(
        alias="path",
        description="Specify the repositories and folders to include under this relative path",
    )
    repos: list[RepositoryBranchMapping] = Field(
        default_factory=list,
        alias="repos",
        description="Specify the repositories and branches to include under this relative path",
    )


class GitlabFolderSelector(Selector):
    folders: list[FolderPattern] = Field(
        default_factory=list,
        alias="folders",
        description="Specify the repositories, branches and folders to include under this relative path",
    )


class GitlabMergeRequestSelector(Selector):
    states: List[Literal["opened", "closed", "merged"]] = Field(
        alias="states",
        description="Specify the state of the merge request to match. Allowed values: opened, closed, merged",
        default=["opened"],
    )
    updated_after: float = Field(
        alias="updatedAfter",
        description="Specify the number of days to look back for merge requests (e.g. 90 for last 90 days)",
        default=90,
    )

    @property
    def updated_after_datetime(self) -> datetime:
        """Convert the created_after days to a timezone-aware datetime object."""
        return datetime.now(timezone.utc) - timedelta(days=self.updated_after)


class GitlabMergeRequestResourceConfig(ResourceConfig):
    selector: GitlabMergeRequestSelector
    kind: Literal["merge-request"]


class GitLabFoldersResourceConfig(ResourceConfig):
    selector: GitlabFolderSelector
    kind: Literal["folder"]


class GitlabPortAppConfig(PortAppConfig):
    resources: list[
        ProjectResourceConfig
        | GitlabGroupWithMembersResourceConfig
        | GitlabMemberResourceConfig
        | GitLabFoldersResourceConfig
        | GitLabFilesResourceConfig
        | GitlabMergeRequestResourceConfig
        | ResourceConfig
    ] = Field(default_factory=list)
    access_config: GitlabAccessConfig = Field(
        default_factory=GitlabAccessConfig,
        alias="accessConfig",
        description="Configuration for GitLab access level filtering",
    )


class GitManipulationHandler(JQEntityProcessor):
    async def _search(self, data: dict[str, Any], pattern: str) -> Any:
        entity_processor: Type[JQEntityProcessor]

        if pattern.startswith(FILE_PROPERTY_PREFIX):
            entity_processor = FileEntityProcessor
        elif pattern.startswith(SEARCH_PROPERTY_PREFIX):
            entity_processor = SearchEntityProcessor
        else:
            entity_processor = JQEntityProcessor

        return await entity_processor(self.context)._search(data, pattern)


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
