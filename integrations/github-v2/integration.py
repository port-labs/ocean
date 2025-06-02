from typing import Literal
from pydantic import Field

from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers import JQEntityProcessor
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


class RepositorySelector(Selector):
    include_archived: bool = Field(
        alias="includeArchived",
        default=False,
        description="Whether to include archived repositories, defaults to false",
    )


class RepositoryResourceConfig(ResourceConfig):
    kind: Literal["repository"]
    selector: RepositorySelector


class PullRequestSelector(Selector):
    state: str = Field(
        default="all",
        description="Filter pull requests by state: open, closed, or all",
    )


class PullRequestResourceConfig(ResourceConfig):
    kind: Literal["pull-request"]
    selector: PullRequestSelector


class IssueSelector(Selector):
    state: str = Field(
        default="all",
        description="Filter issues by state: open, closed, or all",
    )


class IssueResourceConfig(ResourceConfig):
    kind: Literal["issue"]
    selector: IssueSelector


class TeamSelector(Selector):
    privacy: str = Field(
        default="all",
        description="Filter teams by privacy: secret, closed, or all",
    )


class TeamResourceConfig(ResourceConfig):
    kind: Literal["team"]
    selector: TeamSelector


class WorkflowSelector(Selector):
    state: str = Field(
        default="all",
        description="Filter workflows by state: active, deleted, or all",
    )


class WorkflowResourceConfig(ResourceConfig):
    kind: Literal["workflow"]
    selector: WorkflowSelector


class GitHubPortAppConfig(PortAppConfig):
    resources: list[
        RepositoryResourceConfig
        | PullRequestResourceConfig
        | IssueResourceConfig
        | TeamResourceConfig
        | WorkflowResourceConfig
        | ResourceConfig
    ] = Field(default_factory=list)


class GitHubManipulationHandler(JQEntityProcessor):
    pass


class GitHubHandlerMixin(HandlerMixin):
    EntityProcessorClass = GitHubManipulationHandler


class GitHubLiveEventsProcessorManager(LiveEventsProcessorManager, GitHubHandlerMixin):
    pass


class GitHubIntegration(BaseIntegration):
    EntityProcessorClass = GitHubManipulationHandler

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GitHubPortAppConfig

    def __init__(self, context: PortOceanContext):
        super().__init__(context)

        # Replace default webhook manager with GitHub-specific one
        self.context.app.webhook_manager = GitHubLiveEventsProcessorManager(
            self.context.app.integration_router,
            signal_handler,
            self.context.config.max_event_processing_seconds,
            self.context.config.max_wait_seconds_before_shutdown,
        )
