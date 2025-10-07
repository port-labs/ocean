from typing import Literal

from pydantic import Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from port_ocean.core.handlers.webhook.processor_manager import (
    LiveEventsProcessorManager,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    LiveEventTimestamp,
)
from port_ocean.utils.signal import signal_handler
from port_ocean.context.ocean import PortOceanContext
from fastapi import Request
from loguru import logger



def get_default_user_fields() -> str:
    """Default list of fields to fetch for users.

    Matches previous behavior from okta.core.options.get_default_user_fields.
    """
    return (
        "id,status,created,activated,lastLogin,lastUpdated,"
        "profile:(login,firstName,lastName,displayName,email,title,department,"
        "employeeNumber,mobilePhone,primaryPhone,streetAddress,city,state,zipCode,countryCode)"
    )


class OktaUserSelector(Selector):
    """Selector for Okta users."""

    include_groups: bool = Field(
        default=True,
        description="Include user groups in the response",
    )
    include_applications: bool = Field(
        default=True,
        description="Include user applications in the response",
    )
    fields: str = Field(
        default_factory=get_default_user_fields,
        description="Comma-separated list of user fields to retrieve. Profile attributes should be contained within a profile:(field1,field2,...) directive.",
    )


class OktaUserConfig(ResourceConfig):
    """Configuration for Okta users."""

    selector: OktaUserSelector
    kind: Literal["okta-user"]


class OktaAppConfig(PortAppConfig):
    """Port app configuration for Okta integration."""

    resources: list[OktaUserConfig | ResourceConfig] = Field(
        default_factory=list,
        description="Specify the resources to include in the sync",
    )


class OktaHandlerMixin(HandlerMixin):
    pass


class OktaLiveEventsProcessorManager(LiveEventsProcessorManager, OktaHandlerMixin):
    """Custom manager to handle Okta verification challenge at the route level."""

    def _register_route(self, path: str) -> None:
        async def handle_webhook(request: Request) -> dict[str, str]:
            if request.method == "GET":
                challenge = request.headers.get("x-okta-verification-challenge")
                if challenge:
                    logger.info(
                        "Responding to Okta verification challenge", webhook_path=path
                    )
                    return {"verification": challenge}
                else:
                    return {"status": "method_not_allowed"}

            try:
                webhook_event = await WebhookEvent.from_request(request)
                webhook_event.set_timestamp(LiveEventTimestamp.AddedToQueue)
                await self._event_queues[path].put(webhook_event)
                return {"status": "ok"}
            except Exception as e:
                logger.exception(f"Error processing webhook: {str(e)}")
                return {"status": "error", "message": str(e)}

        # Register route on the integration router
        self._router.add_api_route(path, handle_webhook, methods=["POST", "GET"])


class OktaIntegration(BaseIntegration, OktaHandlerMixin):
    """Okta integration class with custom webhook manager for verification support."""

    def __init__(self, context: PortOceanContext):
        super().__init__(context)
        # Replace the Ocean's webhook manager with our custom one (integration-local change)
        self.context.app.webhook_manager = OktaLiveEventsProcessorManager(
            self.context.app.integration_router,
            signal_handler,
            self.context.config.max_event_processing_seconds,
            self.context.config.max_wait_seconds_before_shutdown,
        )

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = OktaAppConfig

