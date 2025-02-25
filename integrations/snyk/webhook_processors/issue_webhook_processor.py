import hashlib
import hmac
import json
from IntegrationKind import IntegrationKind
from initialize_client import init_client
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.context.ocean import ocean


class IssueWebhookProcessor(AbstractWebhookProcessor):
    def should_process_event(self, event: WebhookEvent) -> bool:
        signature = event.headers.get("x-hub-signature", "")
        hmac_obj = hmac.new(
            ocean.integration_config["webhook_secret"].encode("utf-8"),
            json.dumps(event.payload, separators=(",", ":")).encode("utf-8"),
            hashlib.sha256,
        )
        expected_signature = f"sha256={hmac_obj.hexdigest()}"
        return signature == expected_signature

    def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [IntegrationKind.ISSUE]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "project" in payload

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        snyk_client = init_client()

        project_id = payload["project"]["id"]
        organization_id = payload["org"]["id"]

        data_to_update = await snyk_client.get_issues(organization_id, project_id)

        return WebhookEventRawResults(
            updated_raw_results=data_to_update, deleted_raw_results=[]
        )
