from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from kinds import Kinds
from jira_server.webhook_processors.events import (
    JiraProjectEvents,
    JiraDeletedProjectEvent,
)
from jira_server.webhook_processors.processors._base_webhook_processor import (
    _BaseJiraWebhookProcessor,
)
from jira_server.webhook_processors.initialize_client import init_webhook_client


class ProjectWebhookProcessor(_BaseJiraWebhookProcessor):

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.PROJECT]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        event_type = event.payload.get("webhookEvent")
        return event_type in JiraProjectEvents

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "webhookEvent" in payload and "project" in payload

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        project = payload["project"]
        event_type = payload["webhookEvent"]
        logger.info(
            f"Processing project webhook event: {event_type} for project {project['key']}"
        )

        results = WebhookEventRawResults(
            updated_raw_results=[],
            deleted_raw_results=[],
        )

        if event_type == JiraDeletedProjectEvent:
            results.deleted_raw_results.append(project)
        else:
            client = init_webhook_client()
            project_info = await client.get_single_project(project["key"])
            if project_info:
                results.updated_raw_results.append(project_info)

        return results
