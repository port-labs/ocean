from webhook.events import JOB_DELETE_EVENTS, JOB_UPSERT_EVENTS
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from webhook.webhook_processors.jenkins_abstract_webhook_processor import (
    _JenkinsAbstractWebhookProcessor,
)
from client import JenkinsClient
from utils import ObjectKind
from loguru import logger
from urllib.parse import urljoin


class JobWebhookProcessor(_JenkinsAbstractWebhookProcessor):
    """Processes job-related webhook events from Jenkins."""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """
        Validate that this is a job event we should process.
        """
        return event.payload.get("type") in JOB_UPSERT_EVENTS + JOB_DELETE_EVENTS

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.JOB]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the job webhook event and return the raw results."""

        event_type = payload["type"]
        url = payload["url"]
        client = JenkinsClient.create_from_ocean_configuration()

        logger.info(f"Processing job event: {event_type} for job {url}")

        if event_type in JOB_DELETE_EVENTS:
            deleted_job = payload["data"]
            deleted_job["url"] = urljoin(client.jenkins_base_url, url)

            logger.info(f"Job #{url} was deleted")

            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[deleted_job],
            )

        latest_job = await client.get_single_resource(url)

        logger.info(f"Successfully fetched latest data for job {url}")

        return WebhookEventRawResults(
            updated_raw_results=[latest_job], deleted_raw_results=[]
        )
