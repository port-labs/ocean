import httpx
from typing import cast

from initialize_client import init_client
from integration import ObjectKind
from datadog.overrides import SLOResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from datadog.core.exporters import SloExporter
from datadog.core.exporters.slo_exporter import GetSloOptions
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseProcessor,
)


class SloWebhookProcessor(BaseProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return (
            await super().should_process_event(event)
            and self.extract_asset_type(event.payload) == ObjectKind.SLO
        )

    async def get_matching_kinds(self, _: WebhookEvent) -> list[str]:
        return [ObjectKind.SLO]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        slo_id = self.extract_asset_id(payload)
        if slo_id is None:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if self.is_delete_event(payload):
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"id": slo_id}],
            )

        config = cast(SLOResourceConfig, resource_config)
        dd_client = init_client()
        slo_exporter = SloExporter(dd_client)
        try:
            slo = await slo_exporter.get_resource(
                GetSloOptions(
                    id=slo_id,
                    include_restriction_policy=config.selector.include_restriction_policy,
                )
            )
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 404:
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[{"id": slo_id}],
                )
            raise

        return WebhookEventRawResults(
            updated_raw_results=[slo] if slo else [],
            deleted_raw_results=[],
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        return self.extract_asset_id(payload) is not None
