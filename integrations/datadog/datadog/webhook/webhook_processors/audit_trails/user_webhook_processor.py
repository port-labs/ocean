import httpx

from initialize_client import init_client
from integration import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from datadog.core.exporters import UserExporter
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseProcessor,
)


class UserWebhookProcessor(BaseProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return (
            await super().should_process_event(event)
            and self.extract_asset_type(event.payload) == ObjectKind.USER
        )

    async def get_matching_kinds(self, _: WebhookEvent) -> list[str]:
        return [ObjectKind.USER]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        del resource_config
        user_id = self.extract_asset_id(payload)
        if user_id is None:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if self.is_delete_event(payload):
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"id": user_id}],
            )

        dd_client = init_client()
        user_exporter = UserExporter(dd_client)
        try:
            user = await user_exporter.get_resource(user_id)
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 404:
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[{"id": user_id}],
                )
            raise

        return WebhookEventRawResults(
            updated_raw_results=[user] if user else [],
            deleted_raw_results=[],
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        return self.extract_asset_id(payload) is not None
