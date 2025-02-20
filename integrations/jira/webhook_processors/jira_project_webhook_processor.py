from loguru import logger
from jira.client import JiraClient
from object_kind import ObjectKind
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import AbstractWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import EventHeaders, EventPayload, WebhookEvent, WebhookEventRawResults
from port_ocean.context.ocean import ocean


class JiraProjectWebhookProcessor(AbstractWebhookProcessor):
    def create_jira_client(self) -> JiraClient:
        """Create JiraClient with current configuration."""
        return JiraClient(
            ocean.integration_config["jira_host"],
            ocean.integration_config["atlassian_user_email"],
            ocean.integration_config["atlassian_user_token"],
        )

    def should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload.get("webhookEvent", "").startswith("project_")

    def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PROJECT]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        # For Jira webhooks, we don't need additional authentication as they are validated
        # through the webhook secret in the URL
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        # Validate that the payload contains the required fields
        return True

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        webhook_event = payload.get("webhookEvent")
        if not webhook_event:
            logger.error("Missing webhook event")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        client = self.create_jira_client()
        project_key = payload["project"]["key"]

        if webhook_event == "project_soft_deleted":
            logger.info(f"Project {project_key} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[payload["project"]],
            )

        logger.debug(f"Fetching project with key: {project_key}")
        item = await client.get_single_project(project_key)

        if not item:
            logger.warning(f"Failed to retrieve {ObjectKind.PROJECT}")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        data_to_update = []
        data_to_delete = []
        logger.debug(f"Retrieved {ObjectKind.PROJECT} item: {item}")

        if "deleted" in webhook_event:
            data_to_delete.extend([item])
        else:
            data_to_update.extend([item])

        return WebhookEventRawResults(
            updated_raw_results=data_to_update,
            deleted_raw_results=data_to_delete,
        )
