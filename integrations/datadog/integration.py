from enum import StrEnum
from uuid import uuid4

from fastapi import Request
from loguru import logger
from port_ocean.context.ocean import ocean, PortOceanContext
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.webhook.processor_manager import (
    LiveEventsProcessorManager,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    LiveEventTimestamp,
    WebhookEvent,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.utils.signal import signal_handler

from datadog.overrides import DataDogPortAppConfig
from datadog.webhook.webhook_client import AUDIT_TRAIL_WEBHOOK_PATH


class ObjectKind(StrEnum):
    SERVICE_DEPENDENCY = "serviceDependency"
    HOST = "host"
    MONITOR = "monitor"
    SLO = "slo"
    SERVICE = "service"
    SLO_HISTORY = "sloHistory"
    SERVICE_METRIC = "serviceMetric"
    TEAM = "team"
    USER = "user"
    ROLE = "role"
    ORG = "org"


class DatadogLiveEventsProcessorManager(LiveEventsProcessorManager):
    """Custom webhook manager that splits audit-trail batch payloads into
    individual queue entries so each processor sees exactly one event."""

    def _register_route(self, path: str) -> None:
        if path != AUDIT_TRAIL_WEBHOOK_PATH:
            # Monitor-events and any other paths use the standard behaviour
            return super()._register_route(path)

        async def handle_audit_trail(request: Request) -> dict[str, str]:
            try:
                headers = dict(request.headers)
                body = await request.json()
                events = body if isinstance(body, list) else [body]

                for raw_event in events:
                    if not isinstance(raw_event, dict):
                        continue
                    webhook_event = WebhookEvent(
                        trace_id=str(uuid4()),
                        payload=raw_event,
                        headers=headers,
                    )
                    webhook_event.set_timestamp(LiveEventTimestamp.AddedToQueue)
                    if ocean.config.events_debug_logging:
                        self._log_webhook_event(webhook_event)
                    await self._event_queues[path].put(webhook_event)

                return {"status": "ok"}
            except Exception as e:
                logger.exception(f"Error processing audit-trail webhook: {e}")
                return {"status": "error", "message": str(e)}

        self._router.add_api_route(path, handle_audit_trail, methods=["POST"])


class DatadogIntegration(BaseIntegration):
    def __init__(self, context: PortOceanContext) -> None:
        super().__init__(context)
        self.context.app.webhook_manager = DatadogLiveEventsProcessorManager(
            self.context.app.integration_router,
            signal_handler,
            self.context.config.max_event_processing_seconds,
            self.context.config.max_wait_seconds_before_shutdown,
        )

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = DataDogPortAppConfig
