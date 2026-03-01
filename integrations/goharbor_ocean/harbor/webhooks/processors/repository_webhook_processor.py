from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from harbor.clients.client_factory import HarborClientFactory
from harbor.core.exporters.repository_exporter import HarborRepositoryExporter
from harbor.helpers.utils import ObjectKind
from harbor.webhooks.base import HarborAbstractBaseWebhookProcessor
from harbor.webhooks.events import HarborEventType


class RepositoryWebhookProcessor(HarborAbstractBaseWebhookProcessor):
    """Process Harbor repository webhook events.

    Handles events that affect repositories:
    - PUSH_ARTIFACT: New artifact pushed
    - DELETE_ARTIFACT: Artifact deleted (may affect repository state)
    - REPLICATION: Repository replicated
    """

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Check if event affects repositories."""
        event_type = event.payload.get("type")

        return event_type in [
            HarborEventType.PUSH_ARTIFACT,
            HarborEventType.DELETE_ARTIFACT,
            HarborEventType.REPLICATION,
        ]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Get resource kinds this event affects."""
        return [ObjectKind.REPOSITORY]

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate webhook payload structure."""
        required_fields = ["type", "event_data"]
        return all(field in payload for field in required_fields)

    async def handle_event(
        self,
        payload: EventPayload,
        resource: ResourceConfig,
    ) -> WebhookEventRawResults:
        """Process repository webhook event."""
        event_type = payload.get("type")
        event_data = payload.get("event_data", {})

        logger.info(f"Processing Harbor repository webhook event: {event_type}")

        repository = event_data.get("repository", {})
        project_name = repository.get("namespace")
        repository_name = repository.get("name")
        repository_full_name = repository.get("repo_full_name", f"{project_name}/{repository_name}")

        if not project_name or not repository_name:
            logger.warning(f"Missing repository info in webhook payload: {payload}")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        client = HarborClientFactory.get_client()
        exporter = HarborRepositoryExporter(client)

        match event_type:
            case HarborEventType.DELETE_ARTIFACT:
                try:
                    repo = await client.get_repository(project_name, repository_name)

                    if not repo:
                        logger.info(f"Repository {repository_full_name} no longer exists")
                        return WebhookEventRawResults(
                            updated_raw_results=[],
                            deleted_raw_results=[
                                {
                                    "name": repository_name,
                                    "namespace": project_name,
                                }
                            ],
                        )

                    if repo.get("artifact_count", 0) == 0:
                        logger.info(f"Repository {repository_full_name} is now empty")

                    return WebhookEventRawResults(
                        updated_raw_results=[repo],
                        deleted_raw_results=[],
                    )

                except Exception as e:
                    logger.error(f"Failed to check repository {repository_full_name}: {e}")
                    return WebhookEventRawResults(
                        updated_raw_results=[],
                        deleted_raw_results=[],
                    )

            case HarborEventType.PUSH_ARTIFACT | HarborEventType.REPLICATION:
                try:
                    repo = await exporter.get_resource(project_name, repository_name)

                    logger.info(f"Successfully fetched updated repository: {repository_full_name}")

                    return WebhookEventRawResults(
                        updated_raw_results=[repo],
                        deleted_raw_results=[],
                    )
                except Exception as e:
                    logger.error(f"Failed to fetch repository {repository_full_name}: {e}")
                    return WebhookEventRawResults(
                        updated_raw_results=[],
                        deleted_raw_results=[],
                    )

            case _:
                logger.warning(f"Unhandled event type: {event_type}")
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[],
                )
