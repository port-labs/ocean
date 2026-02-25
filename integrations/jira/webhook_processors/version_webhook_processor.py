from typing import cast

from loguru import logger

from initialize_client import create_jira_client
from jira.overrides import JiraProjectResourceConfig
from kinds import Kinds
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


class VersionWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload.get("webhookEvent", "").startswith("jira:version_")

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.PROJECT]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        version = payload.get("version")
        return version is not None and (
            version.get("id") is not None or "projectId" in version
        )

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        project_config = cast(JiraProjectResourceConfig, resource_config)
        if not project_config.selector.include_releases:
            logger.debug(
                "Skipping version event: project resource has includeReleases disabled"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        version = payload["version"]
        project_identifier = version.get("key") or str(version["projectId"])

        client = create_jira_client()
        project = await client.get_project_with_releases(project_identifier)
        logger.info(f"Refreshed project {project['key']} releases after version event")
        return WebhookEventRawResults(
            updated_raw_results=[project],
            deleted_raw_results=[],
        )
