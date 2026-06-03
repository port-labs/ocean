import httpx

from initialize_client import init_client
from integration import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from datadog.core.exporters import RoleExporter
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseProcessor,
)


class RoleWebhookProcessor(BaseProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return (
            await super().should_process_event(event)
            and self.extract_asset_type(event.payload) == ObjectKind.ROLE
        )

    async def get_matching_kinds(self, _: WebhookEvent) -> list[str]:
        return [ObjectKind.ROLE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        del resource_config
        role_id = self.extract_asset_id(payload)
        if role_id is None:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if self.is_delete_event(payload):
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"id": role_id}],
            )

        dd_client = init_client()
        role_exporter = RoleExporter(dd_client)
        try:
            role = await role_exporter.get_resource(role_id)
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 404:
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[{"id": role_id}],
                )
            raise

        return WebhookEventRawResults(
            updated_raw_results=[role] if role else [],
            deleted_raw_results=[],
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        return self.extract_asset_id(payload) is not None
