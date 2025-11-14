from IntegrationKind import IntegrationKind
from initialize_client import init_client
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from snyk.utils import enrich_batch_with_org, get_matching_organization
from webhook_processors.snyk_base_webhook_processor import SnykBaseWebhookProcessor


class ProjectWebhookProcessor(SnykBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [IntegrationKind.PROJECT]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        # no deletion in snyk events https://docs.snyk.io/snyk-api/how-to-use-snyk-webhooks-apis/webhooks
        snyk_client = init_client()

        project_id = payload["project"]["id"]
        organization_id = payload["org"]["id"]
        organization = get_matching_organization(
            await snyk_client.get_all_organizations(), organization_id
        )
        project_details = await snyk_client.get_single_project(
            organization_id, project_id
        )
        if organization:
            item_to_upsert = enrich_batch_with_org([project_details], organization)
        else:
            item_to_upsert = [project_details]

        return WebhookEventRawResults(
            updated_raw_results=item_to_upsert, deleted_raw_results=[]
        )
