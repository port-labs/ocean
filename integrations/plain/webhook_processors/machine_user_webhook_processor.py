from __future__ import annotations

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from plain.client import PlainClient
from plain.constants import MACHINE_USER_EVENTS
from plain.utils import ObjectKind
from webhook_processors.plain_abstract_webhook_processor import (
    PlainAbstractWebhookProcessor,
)
from webhook_processors.utils import assignee_machine_user_id, event_payload


class MachineUserWebhookProcessor(PlainAbstractWebhookProcessor):
    """Plain has no machineUser.* webhooks; refresh from assignment transitions."""

    def get_event_types(self) -> set[str]:
        return set(MACHINE_USER_EVENTS)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.MACHINE_USER]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        body = event_payload(payload)
        machine_user_id = assignee_machine_user_id(body)
        if not machine_user_id:
            logger.info(
                "Plain assignment webhook has no machine user assignee; "
                "skipping machine user sync"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        exclude_deleted = bool(
            getattr(resource_config.selector, "exclude_deleted", False)
        )
        client = PlainClient()
        machine_user = await client.get_machine_user(machine_user_id)
        if exclude_deleted and machine_user.get("isDeleted"):
            logger.info(
                "Plain machine user {} is deleted and excludeDeleted is set; deleting",
                machine_user_id,
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[machine_user]
            )

        logger.info("Upserting Plain machine user {}", machine_user_id)
        return WebhookEventRawResults(
            updated_raw_results=[machine_user],
            deleted_raw_results=[],
        )
