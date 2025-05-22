
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

from github.entity_processors.entity_processor import FileEntityProcessor, SearchEntityProcessor


FILE_PROPERTY_PREFIX = "file://"
SEARCH_PROPERTY_PREFIX = "search://"


class RepositorySelector(Selector):
    """Selector for GitHub repositories."""
    include_languages: bool = Field(
        alias="includeLanguages",
        default=False,
        description="Whether to include the languages of the repository, defaults to false",
    )


class RepositoryResourceConfig(ResourceConfig):
    """Resource configuration for GitHub repositories."""
    kind: Literal["repository"]
    selector: RepositorySelector


class GitHubMemberSelector(Selector):
    """Selector for GitHub members."""
    include_bot_members: bool = Field(
        alias="includeBotMembers",
        default=False,
        description="If set to false, bots will be filtered out from the members list. Default value is false",
    )


class GitHubTeamWithMembersResourceConfig(ResourceConfig):
    """Resource configuration for GitHub teams with members."""
    kind: Literal["team-with-members"] # type: ignore
    selector: GitHubMemberSelector # type: ignore


class GitHubMemberResourceConfig(ResourceConfig):
    """Resource configuration for GitHub members."""
    kind: Literal["member"]
    selector: GitHubMemberSelector


class GitHubPullRequestResourceConfig(ResourceConfig):
    """Resource configuration for GitHub pull requests."""
    kind: Literal["pull-request"]
    selector: Selector


class GitHubPortAppConfig(PortAppConfig):
    """Port app configuration for GitHub integration."""
    resources: list[
        RepositoryResourceConfig
        | GitHubTeamWithMembersResourceConfig
        | GitHubMemberResourceConfig
        | GitHubPullRequestResourceConfig
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
        elif pattern.startswith(SEARCH_PROPERTY_PREFIX):
            entity_processor = SearchEntityProcessor
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

        # Replace default webhook manager with GitHub-specific one
        self.context.app.webhook_manager = GitHubLiveEventsProcessorManager(
            self.context.app.integration_router,
            signal_handler,
            self.context.config.max_event_processing_seconds,
            self.context.config.max_wait_seconds_before_shutdown,
        )
