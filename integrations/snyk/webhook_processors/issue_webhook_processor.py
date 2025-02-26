from IntegrationKind import IntegrationKind
from initialize_client import init_client
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from webhook_processors.snyk_base_webhook_processor import SnykBaseWebhookProcessor


class IssueWebhookProcessor(SnykBaseWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        # snyk has 2 api versions: v1 and REST API
        # snyk does not provide a way to map v1 issue id into REST API issue id
        # on webhook event we get in the payload newIssues and removedIssues in v1 schema but the data for the mapping is in the REST API schema
        # so we need to fetch the data from the REST API to map data to entity
        # checkout: https://docs.snyk.io/snyk-api/api-endpoints-index-and-tips/issue-ids-in-snyk-apis
        return False

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [IntegrationKind.ISSUE]

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
