from webhook.events import BUILD_DELETE_EVENTS, BUILD_UPSERT_EVENTS
from webhook.webhook_processors.jenkins_abstract_webhook_processor import (
    _JenkinsAbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from client import JenkinsClient
from utils import ObjectKind
from loguru import logger
from urllib.parse import urljoin


class BuildWebhookProcessor(_JenkinsAbstractWebhookProcessor):
    """Processes build-related webhook events from Jenkins."""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """
        Validate that this is a build event we should process.
        """
        return event.payload.get("type") in BUILD_UPSERT_EVENTS + BUILD_DELETE_EVENTS

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.BUILD]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the build webhook event and return the raw results."""

        event_type = payload["type"]
        source = payload["source"]
        url = payload["url"]
        client = JenkinsClient.create_from_ocean_configuration()

        logger.info(
            f"Processing build event: {event_type} for identifier: {url} and source {source}"
        )

        if event_type in BUILD_DELETE_EVENTS:
            deleted_build = payload["data"]
            deleted_build["url"] = urljoin(client.jenkins_base_url, url)

            logger.info(f"Build #{url} was deleted from {source}")

            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[deleted_build],
            )

        latest_build = await client.get_single_resource(url)

        logger.info(f"Successfully fetched latest data for build {url} from {source}")

        return WebhookEventRawResults(
            updated_raw_results=[latest_build], deleted_raw_results=[]
        )
