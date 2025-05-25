
from typing import Literal, Any, Type
from pydantic import BaseModel, Field

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

from github.entity_processors.entity_processor import FileEntityProcessor


FILE_PROPERTY_PREFIX = "file://"




class RepositoryResourceConfig(ResourceConfig):
    """Resource configuration for GitHub repositories."""
    kind: Literal["repository"]
    selector: Selector


class GitHubTeamWithMembersResourceConfig(ResourceConfig):
    """Resource configuration for GitHub teams with members."""
    kind: Literal["team"] # type: ignore
    selector: Selector


class GitHubMemberResourceConfig(ResourceConfig):
    """Resource configuration for GitHub members."""
    kind: Literal["member"]
    selector: Selector


class GitHubPullRequestResourceConfig(ResourceConfig):
    """Resource configuration for GitHub pull requests."""
    kind: Literal["pull-request"]
    selector: Selector

class GitHubWorkflowResourceConfig(ResourceConfig):
    """Resource configuration for GitHub workflows."""
    kind: Literal["workflow"]
    selector: Selector

class GitHubIssueResourceConfig(ResourceConfig):
    """Resource configuration for GitHub issues."""
    kind: Literal["issue"]
    selector: Selector


class GitHubPortAppConfig(PortAppConfig):
    """Port app configuration for GitHub integration."""
    resources: list[
        RepositoryResourceConfig
        | GitHubTeamWithMembersResourceConfig
        | GitHubMemberResourceConfig
        | GitHubPullRequestResourceConfig
        | GitHubIssueResourceConfig
        | GitHubWorkflowResourceConfig
        | ResourceConfig
    ] = Field(default_factory=list)


class GitManipulationHandler(JQEntityProcessor):
    """Handler for file and search references in JQ expressions."""

    async def _search(self, data: dict[str, Any], pattern: str) -> Any:
        """
        Process a reference pattern.

        Args:
            data: Entity data
            pattern: Reference pattern

        Returns:
            Processed result
        """
        entity_processor: Type[JQEntityProcessor]

        if pattern.startswith(FILE_PROPERTY_PREFIX):
            entity_processor = FileEntityProcessor
        else:
            entity_processor = JQEntityProcessor

        return await entity_processor(self.context)._search(data, pattern)


class GitHubHandlerMixin(HandlerMixin):
    """Mixin for GitHub entity processing."""
    EntityProcessorClass = GitManipulationHandler


class GitHubLiveEventsProcessorManager(LiveEventsProcessorManager, GitHubHandlerMixin):
    """Manager for GitHub webhook events."""
    pass


class GitHubIntegration(BaseIntegration):
    """Main GitHub integration class."""

    EntityProcessorClass = GitManipulationHandler

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GitHubPortAppConfig

    def __init__(self, context: PortOceanContext):
        super().__init__(context)

        self.context.app.webhook_manager = GitHubLiveEventsProcessorManager(
            self.context.app.integration_router,
            signal_handler,
            self.context.config.max_event_processing_seconds,
            self.context.config.max_wait_seconds_before_shutdown,
        )
