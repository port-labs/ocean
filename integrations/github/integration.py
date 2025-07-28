from pydantic import BaseModel, Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.entity_processor.jq_entity_processor import (
    JQEntityProcessor,
)
from port_ocean.core.handlers.webhook.processor_manager import (
    LiveEventsProcessorManager,
)
from github.entity_processors.file_entity_processor import FileEntityProcessor
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from typing import Any, Optional, Type, Literal
from loguru import logger
from port_ocean.utils.signal import signal_handler
from github.helpers.utils import ObjectKind


FILE_PROPERTY_PREFIX = "file://"


class GithubRepositorySelector(Selector):
    include: Optional[Literal["collaborators", "teams"]] = Field(
        default=None,
        description="Specify the relationship to include in the repository",
    )


class GithubRepositoryConfig(ResourceConfig):
    selector: GithubRepositorySelector
    kind: Literal["repository"]


class RepositoryBranchMapping(BaseModel):
    name: str = Field(
        description="Specify the repository name",
    )
    branch: Optional[str] = Field(
        default=None,
        description="Specify the branch to bring the folders from, repo's default branch will be used if none is passed",
    )


class FolderSelector(BaseModel):
    path: str = Field(default="*")
    repos: list[RepositoryBranchMapping]


class GithubFolderSelector(Selector):
    folders: list[FolderSelector]


class GithubFolderResourceConfig(ResourceConfig):
    selector: GithubFolderSelector
    kind: Literal[ObjectKind.FOLDER]


class GithubPullRequestSelector(Selector):
    state: Literal["open", "closed", "all"] = Field(
        default="open",
        description="Filter by pull request state (e.g., open, closed, all)",
    )


class GithubPullRequestConfig(ResourceConfig):
    selector: GithubPullRequestSelector
    kind: Literal["pull-request"]


class GithubIssueSelector(Selector):
    state: Literal["open", "closed", "all"] = Field(
        default="open",
        description="Filter by issue state (open, closed, all)",
    )


class GithubIssueConfig(ResourceConfig):
    selector: GithubIssueSelector
    kind: Literal["issue"]


class GithubTeamSector(Selector):
    members: bool = Field(default=True)


class GithubTeamConfig(ResourceConfig):
    selector: GithubTeamSector
    kind: Literal[ObjectKind.TEAM]


class GithubDependabotAlertSelector(Selector):
    states: list[Literal["auto_dismissed", "dismissed", "fixed", "open"]] = Field(
        default=["open"],
        description="Filter alerts by state (auto_dismissed, dismissed, fixed, open)",
    )


class GithubDependabotAlertConfig(ResourceConfig):
    selector: GithubDependabotAlertSelector
    kind: Literal["dependabot-alert"]


class GithubCodeScanningAlertSelector(Selector):
    state: Literal["open", "closed", "dismissed", "fixed"] = Field(
        default="open",
        description="Filter alerts by state (open, closed, dismissed, fixed)",
    )


class GithubCodeScanningAlertConfig(ResourceConfig):
    selector: GithubCodeScanningAlertSelector
    kind: Literal["code-scanning-alerts"]


class GithubFilePattern(BaseModel):
    path: str = Field(
        alias="path",
        description="Specify the path to match files from",
    )
    repos: Optional[list[RepositoryBranchMapping]] = Field(
        alias="repos",
        description="Specify the repositories and branches to fetch files from",
        default=None,
    )
    skip_parsing: bool = Field(
        default=False,
        alias="skipParsing",
        description="Skip parsing the files and just return the raw file content",
    )
    validation_check: bool = Field(
        default=False,
        alias="validationCheck",
        description="Enable validation for this file pattern during pull request processing",
    )


class GithubFileSelector(Selector):
    files: list[GithubFilePattern]


class GithubFileResourceConfig(ResourceConfig):
    kind: Literal["file"]
    selector: GithubFileSelector


class GithubPortAppConfig(PortAppConfig):
    repository_type: str = Field(alias="repositoryType", default="all")
    resources: list[
        GithubRepositoryConfig
        | GithubPullRequestConfig
        | GithubIssueConfig
        | GithubDependabotAlertConfig
        | GithubCodeScanningAlertConfig
        | GithubFolderResourceConfig
        | GithubTeamConfig
        | GithubFileResourceConfig
        | ResourceConfig
    ]


class GitManipulationHandler(JQEntityProcessor):
    async def _search(self, data: dict[str, Any], pattern: str) -> Any:
        entity_processor: Type[JQEntityProcessor]
        if pattern.startswith(FILE_PROPERTY_PREFIX):
            entity_processor = FileEntityProcessor
        else:
            entity_processor = JQEntityProcessor
        return await entity_processor(self.context)._search(data, pattern)


class GithubHandlerMixin(HandlerMixin):
    EntityProcessorClass = GitManipulationHandler


class GithubLiveEventsProcessorManager(LiveEventsProcessorManager, GithubHandlerMixin):
    pass


class GithubIntegration(BaseIntegration, GithubHandlerMixin):
    def __init__(self, context: PortOceanContext):
        logger.info("Initializing Github Integration")
        super().__init__(context)

        # Override the Ocean's default webhook manager with our custom one
        # This is necessary because we need GithubHandlerMixin which provides
        # GitManipulationHandler to handle file:// prefixed properties and enable
        # dynamic switching between JQEntityProcessor and FileEntityProcessor
        # for GitHub-specific file content processing.
        self.context.app.webhook_manager = GithubLiveEventsProcessorManager(
            self.context.app.integration_router,
            signal_handler,
            self.context.config.max_event_processing_seconds,
            self.context.config.max_wait_seconds_before_shutdown,
        )

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GithubPortAppConfig
