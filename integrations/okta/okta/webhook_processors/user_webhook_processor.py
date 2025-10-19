from typing import Any, cast

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from okta.webhook_processors.base_webhook_processor import OktaBaseWebhookProcessor
from okta.webhook_processors.utils import iter_event_targets, any_target_of_type
from okta.clients.client_factory import OktaClientFactory
from okta.utils import ObjectKind
from okta.core.exporters.user_exporter import OktaUserExporter
from okta.core.options import GetUserOptions
from okta.utils import OktaEventType
from integration import OktaUserConfig


class OktaUserWebhookProcessor(OktaBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.USER]

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Check if the event contains user-related events."""
        return any_target_of_type(event.payload, "User")

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = OktaClientFactory.get_client()
        exporter = OktaUserExporter(client)

        okta_config = cast(OktaUserConfig, resource_config)
        selector = okta_config.selector
        include_groups = selector.include_groups
        include_applications = selector.include_applications
        fields = selector.fields

        updated_results: list[dict[str, Any]] = []
        deleted_results: list[dict[str, Any]] = []

        for event_type, target in iter_event_targets(payload):
            if not (target["type"] == "User" and target["id"]):
                continue

            user_id = target["id"]
            is_delete_event = (
                event_type == OktaEventType.USER_LIFECYCLE_DELETE_INITIATED.value
            )

            if is_delete_event:
                deleted_results.append({"id": user_id})
            else:
                user = await exporter.get_resource(
                    GetUserOptions(
                        user_id=user_id,
                        include_groups=include_groups,
                        include_applications=include_applications,
                        fields=fields,
                    )
                )
                updated_results.append(user)

        return WebhookEventRawResults(
            updated_raw_results=updated_results, deleted_raw_results=deleted_results
        )
