from __future__ import annotations
from loguru import logger
from typing import Any

from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from harbor.factory import HarborClientFactory
from harbor.utils.constants import HarborKind
from harbor.webhooks import events
from harbor.webhooks.utils import extract_repository_info, extract_deleted_resources, fetch_artifacts_for_repository, fetch_repository_by_name, fetch_artifacts_for_repository


class ArtifactWebhookProcessor(AbstractWebhookProcessor):
    """Processor for Harbor artifact webhook events"""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        event_type = event.payload.get("type", "")
        return event_type in events.ARTIFACT_EVENTS

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Return the resource kinds this processor handles"""
        return [HarborKind.ARTIFACT]

    async def handle_event(
        self,
        payload: EventPayload,
        resource: ResourceConfig,
    ) -> WebhookEventRawResults:
        event_type = payload.get("type")
        project_name, repo_name = extract_repository_info(payload)

        logger.info(f"Processing {event_type} for {repo_name}")

        if event_type == events.DELETE_ARTIFACT:
            deleted_resources = extract_deleted_resources(payload)
            logger.info(f"Artifact deleted: {len(deleted_resources)} resources")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=deleted_resources
            )

        # Handle push/scan - fetch fresh data
        if not project_name or not repo_name:
            logger.warning("Missing repository information in webhook payload")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        client = HarborClientFactory.get_client()
        artifacts = await fetch_artifacts_for_repository(
            client, project_name, repo_name
        )
        return WebhookEventRawResults(
            updated_raw_results=artifacts, deleted_raw_results=[]
        )

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        # for now, allow all webhooks
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        has_required_fields = "type" in payload and "event_data" in payload

        if not has_required_fields:
            logger.warning("Invalid webhook payload: missing required fields")

        return has_required_fields


class RepositoryWebhookProcessor(AbstractWebhookProcessor):
    """Processes repository-related webhook events"""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        event_type = event.payload.get("type", "")
        return event_type in events.REPOSITORY_EVENTS

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [HarborKind.REPOSITORY]

    async def handle_event(
        self,
        payload: EventPayload,
        resource: ResourceConfig,
    ) -> WebhookEventRawResults:
        """Process repository webhook event and return updated repositories"""
        event_type = payload.get("type")
        project_name, repo_name = extract_repository_info(payload)

        logger.info(f"Processing {event_type} for repository: {repo_name}")

        if not project_name or not repo_name:
            logger.warning("Missing repository information in webhook payload")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        client = HarborClientFactory.get_client()
        repositories = await fetch_repository_by_name(client, project_name, repo_name)

        return WebhookEventRawResults(
            updated_raw_results=repositories, deleted_raw_results=[]
        )

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        has_required_fields = "type" in payload and "event_data" in payload

        if not has_required_fields:
            logger.warning("Invalid webhook payload: missing required fields")

        return has_required_fields
