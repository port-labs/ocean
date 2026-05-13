from typing import cast

from loguru import logger
from azure_devops.webhooks.webhook_processors.base_processor import (
    AzureDevOpsBaseWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from azure_devops.misc import Kind
from azure_devops.webhooks.events import BuildEvents
from azure_devops.client.azure_devops_client import AzureDevopsClient
from integration import AzureDevopsTestRunResourceConfig


class TestRunWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.TEST_RUN]

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not await super().validate_payload(payload):
            return False

        project_id = payload.get("resourceContainers", {}).get("project", {}).get("id")
        build_id = payload.get("resource", {}).get("id")
        return project_id is not None and build_id is not None

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            event_type = event.payload["eventType"]
            return bool(BuildEvents(event_type))
        except (KeyError, ValueError):
            return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = AzureDevopsClient.create_from_ocean_config()
        project_id = payload["resourceContainers"]["project"]["id"]
        build_id = str(payload["resource"]["id"])

        config = cast(AzureDevopsTestRunResourceConfig, resource_config)
        test_runs = await client.get_test_runs_by_build(
            project_id,
            build_id,
            config.selector.include_results,
            config.selector.code_coverage,
        )
        if not test_runs:
            logger.info(
                f"No test runs found for build {build_id} in project {project_id}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        logger.info(
            f"Found {len(test_runs)} test runs for build {build_id} in project {project_id}"
        )
        return WebhookEventRawResults(
            updated_raw_results=test_runs,
            deleted_raw_results=[],
        )
