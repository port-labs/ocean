from consts import BUILD_DELETE_EVENTS, BUILD_UPSERT_EVENTS
from webhook_processors.abstract import JenkinsAbstractWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from client import JenkinsClient
from kinds import ObjectKind
from loguru import logger


class BuildWebhookProcessor(JenkinsAbstractWebhookProcessor):
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

        event_type = payload.get("type")
        source = payload.get("source")
        url = payload.get("url", "")
        build_data = payload.get("data", {})
        client = JenkinsClient.create_from_ocean_configuration()

        logger.info(
            f"Processing build event: {event_type} for identifier: {url} and source {source}"
        )

        if event_type in BUILD_DELETE_EVENTS:
            jenkins_host = client.jenkins_base_url
            build_url = f"{jenkins_host}/{url}"
            job_url = f"{jenkins_host}/{source}"

            deleted_build = {
                "url": build_url,
                "displayName": build_data.get("displayName"),
                "result": build_data.get("result"),
                "duration": build_data.get("duration"),
                "timestamp": build_data.get("timestamp"),
                "parentJob": {"url": job_url},
                "previousBuild": {"url": build_url},
            }

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
