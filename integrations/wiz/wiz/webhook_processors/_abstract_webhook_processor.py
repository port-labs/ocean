from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    EventHeaders,
    WebhookEvent,
)
from port_ocean.context.ocean import ocean
from initialize_client import init_client
from fastapi import HTTPException
from typing import Optional


class WizAbstractWebhookProcessor(AbstractWebhookProcessor):

    _client = init_client()
    _verification_token: Optional[str] = ocean.integration_config[
        "wiz_webhook_verification_token"
    ]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        credentials = headers.get("authorization")
        if (
            not credentials
            or credentials.split(" ")[0] != "Bearer"
            or self._verification_token != credentials.split(" ")[1]
        ):
            raise HTTPException(
                status_code=401,
                detail={
                    "ok": False,
                    "message": "Wiz webhook token verification failed, ignoring request",
                },
            )
        return True

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return True
