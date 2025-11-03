from fastapi import Request
from pydantic import BaseModel, Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.queue import GroupQueue
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    LiveEventTimestamp,
    WebhookEvent,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.entity_processor.jq_entity_processor import (
    JQEntityProcessor,
)
from port_ocean.core.handlers.webhook.processor_manager import (
    LiveEventsProcessorManager,
)
from github.entity_processors.file_entity_processor import FileEntityProcessor
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from typing import Any, Dict, List, Optional, Type, Literal
from loguru import logger
from port_ocean.utils.signal import signal_handler
from github.helpers.utils import ObjectKind
from github.webhook.live_event_group_selector import get_primary_id

FILE_PROPERTY_PREFIX = "file://"


class GithubRepositorySelector(Selector):
    include: Optional[List[Literal["collaborators", "teams"]]] = Field(
        default_factory=list,
        description="Specify the relationships to include in the repository",
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
    organization: Optional[str] = Field(default=None)
    path: str = Field(default="*")
    repos: list[RepositoryBranchMapping]


class GithubFolderSelector(Selector):
    folders: list[FolderSelector]


class GithubUserSelector(Selector):
    include_bots: bool = Field(
        default=True,
        alias="includeBots",
        description="Include bots in the list of users",
    )


class GithubUserConfig(ResourceConfig):
    selector: GithubUserSelector
    kind: Literal[ObjectKind.USER]


class GithubFolderResourceConfig(ResourceConfig):
    selector: GithubFolderSelector
    kind: Literal[ObjectKind.FOLDER]


class GithubPullRequestSelector(Selector):
    states: list[Literal["open", "closed"]] = Field(
        default=["open"],
        description="Filter by pull request state (e.g., open, closed)",
    )
    max_results: int = Field(
        alias="maxResults",
        default=100,
        ge=1,
        le=300,
        description="Limit the number of pull requests returned",
    )
    since: int = Field(
        default=60,
        ge=1,
        le=90,
        description="Only fetch pull requests created within the last N days (1-90 days)",
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


class GithubSecretScanningAlertSelector(Selector):
    state: Literal["open", "resolved", "all"] = Field(
        default="open",
        description="Filter alerts by state (open, resolved, all)",
    )
    hide_secret: bool = Field(
        alias="hideSecret",
        default=True,
        description="Whether to hide the actual secret content in the alert data for security purposes",
    )


class GithubSecretScanningAlertConfig(ResourceConfig):
    selector: GithubSecretScanningAlertSelector
    kind: Literal["secret-scanning-alerts"]


class GithubFilePattern(BaseModel):
    organization: Optional[str] = Field(default=None)
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


class GithubBranchSelector(Selector):
    detailed: bool = Field(
        default=False, description="Include extra details about the branch"
    )
    protection_rules: bool = Field(
        default=False,
        alias="protectionRules",
        description="Include protection rules for the branch",
    )


class GithubBranchConfig(ResourceConfig):
    kind: Literal["branch"]
    selector: GithubBranchSelector


class GithubPortAppConfig(PortAppConfig):
    organizations: List[str] = Field(
        default_factory=list,
        description=(
            "List of GitHub organization names (optional - if not provided, "
            "will sync all organizations the personal access token user is a "
            "member of) for Classic PAT authentication."
        ),
    )
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
        | GithubBranchConfig
        | GithubSecretScanningAlertConfig
        | GithubUserConfig
        | ResourceConfig
    ] = Field(default_factory=list)


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


class GithubLiveEventsGroupProcessorManager(
    LiveEventsProcessorManager, GithubHandlerMixin
):
    def register_processor(
        self, path: str, processor: Type[AbstractWebhookProcessor]
    ) -> None:
        """Register a webhook processor for a specific path with optional filter

        Args:
            path: The webhook path to register
            processor: The processor class to register
            kind: The resource kind to associate with this processor, or None to match any kind
        """
        if not issubclass(processor, AbstractWebhookProcessor):
            raise ValueError("Processor must extend AbstractWebhookProcessor")

        if path not in self._processors_classes:
            self._processors_classes[path] = []
            self._event_queues[path] = GroupQueue(("group_id"))
            self._register_route(path)

        self._processors_classes[path].append(processor)

    def _register_route(self, path: str) -> None:
        async def handle_webhook(request: Request) -> Dict[str, str]:
            """Handle incoming webhook requests for a specific path."""
            try:
                webhook_event = await WebhookEvent.from_request(request)
                webhook_event.set_timestamp(LiveEventTimestamp.AddedToQueue)
                webhook_event.group_id = get_primary_id(webhook_event)
                await self._event_queues[path].put(webhook_event)
                return {"status": "ok"}
            except Exception as e:
                logger.exception(f"Error processing webhook: {str(e)}")
                return {"status": "error", "message": str(e)}

        self._router.add_api_route(
            path,
            handle_webhook,
            methods=["POST"],
        )


class GithubIntegration(BaseIntegration, GithubHandlerMixin):
    def __init__(self, context: PortOceanContext):
        logger.info("Initializing Github Integration")
        super().__init__(context)

        # Override the Ocean's default webhook manager with our custom one
        # This is necessary because we need GithubHandlerMixin which provides
        # GitManipulationHandler to handle file:// prefixed properties and enable
        # dynamic switching between JQEntityProcessor and FileEntityProcessor
        # for GitHub-specific file content processing.
        event_workers_count = context.config.event_workers_count
        ProcessManager = (
            GithubLiveEventsGroupProcessorManager
            if event_workers_count > 1
            else GithubLiveEventsProcessorManager
        )
        self.context.app.webhook_manager = ProcessManager(
            self.context.app.integration_router,
            signal_handler,
            self.context.config.max_event_processing_seconds,
            self.context.config.max_wait_seconds_before_shutdown,
        )

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GithubPortAppConfig
