from pydantic import Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
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
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from typing import Any, Dict, Type, Literal
from loguru import logger
from port_ocean.utils.signal import signal_handler
from fastapi import Request
from fake_org_data.types import FakeIntegrationConfig, FakeObjectKind, FakeSelector
from fake_org_data.fake_client import get_fake_readme_file


class FakePersonConfig(ResourceConfig):
    """Configuration for fake-person resource"""

    selector: FakeSelector
    kind: Literal[FakeObjectKind.FAKE_PERSON]


class FakeDepartmentConfig(ResourceConfig):
    """Configuration for fake-department resource"""

    selector: FakeSelector
    kind: Literal[FakeObjectKind.FAKE_DEPARTMENT]


class FakeFileConfig(ResourceConfig):
    """Configuration for fake-file resource"""

    selector: FakeSelector
    kind: Literal[FakeObjectKind.FAKE_FILE]


class FakeRepositoryConfig(ResourceConfig):
    """Configuration for fake-repository resource"""

    selector: FakeSelector
    kind: Literal[FakeObjectKind.FAKE_REPOSITORY]


class FakePortAppConfig(PortAppConfig):
    """Port app configuration for fake integration"""

    resources: list[
        FakePersonConfig
        | FakeDepartmentConfig
        | FakeFileConfig
        | FakeRepositoryConfig
        | ResourceConfig
    ] = Field(default_factory=list)


FILE_PROPERTY_PREFIX = "file://"


class FakeFileEntityProcessor(JQEntityProcessor):
    prefix = FILE_PROPERTY_PREFIX

    async def _search(self, data: dict[str, Any], pattern: str) -> Any:
        pattern = pattern.replace(self.prefix, "")
        config = FakeIntegrationConfig(
            query="true",
            filePath=pattern,
            entityCount=1,
            entitySizeKb=1,
            delayMs=0,
            itemsToParseEntityCount=1,
            itemsToParseEntitySizeKb=1,
            batchCount=1,
        )
        content = await get_fake_readme_file(config)
        return content


class FakeGitManipulationHandler(JQEntityProcessor):
    prefix = FILE_PROPERTY_PREFIX

    async def _search(self, data: dict[str, Any], pattern: str) -> Any:
        entity_processor: Type[JQEntityProcessor]
        if pattern.startswith(FILE_PROPERTY_PREFIX):
            entity_processor = FakeFileEntityProcessor
        else:
            entity_processor = JQEntityProcessor

        return await entity_processor(self.context)._search(data, pattern)


class FakeHandlerMixin(HandlerMixin):
    """Handler mixin for fake integration with custom entity processor"""

    EntityProcessorClass = FakeGitManipulationHandler


class FakeLiveEventsProcessorManager(LiveEventsProcessorManager, FakeHandlerMixin):
    """Live events processor manager for fake integration"""

    pass


class FakeLiveEventsGroupProcessorManager(LiveEventsProcessorManager, FakeHandlerMixin):
    """Live events group processor manager for fake integration with group support"""

    def register_processor(
        self, path: str, processor: Type[AbstractWebhookProcessor]
    ) -> None:
        """Register a webhook processor for a specific path

        Args:
            path: The webhook path to register
            processor: The processor class to register
        """
        if not issubclass(processor, AbstractWebhookProcessor):
            raise ValueError("Processor must extend AbstractWebhookProcessor")

        if path not in self._processors_classes:
            self._processors_classes[path] = []
            self._event_queues[path] = GroupQueue(("group_id"))
            self._register_route(path)

        self._processors_classes[path].append(processor)

    def _register_route(self, path: str) -> None:
        """Register a route for webhook handling"""

        async def handle_webhook(request: Request) -> Dict[str, str]:
            """Handle incoming webhook requests for a specific path."""
            try:
                webhook_event = await WebhookEvent.from_request(request)
                webhook_event.set_timestamp(LiveEventTimestamp.AddedToQueue)
                # Use person/department ID as group_id for grouping related events
                webhook_event.group_id = "default"

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


class FakeIntegration(BaseIntegration, FakeHandlerMixin):
    """Fake integration with custom handler mixin and webhook manager"""

    def __init__(self, context: PortOceanContext):
        logger.info("Initializing Fake Integration")
        super().__init__(context)

        # Override the Ocean's default webhook manager with our custom one
        # This enables the FakeHandlerMixin which provides FakeEntityProcessor
        # for custom entity processing and webhook handling.
        event_workers_count = context.config.event_workers_count
        ProcessManager = (
            FakeLiveEventsGroupProcessorManager
            if event_workers_count > 1
            else FakeLiveEventsProcessorManager
        )
        processor_manager = ProcessManager(
            self.context.app.integration_router,
            signal_handler,
            self.context.config.max_event_processing_seconds,
            self.context.config.max_wait_seconds_before_shutdown,
        )
        self.context.app.webhook_manager = processor_manager
        self.context.app.execution_manager._webhook_manager = processor_manager

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = FakePortAppConfig
