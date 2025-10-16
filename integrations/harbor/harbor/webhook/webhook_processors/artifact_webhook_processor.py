"""Webhook processor for Harbor artifact events."""

from loguru import logger
from harbor.webhook.events import ARTIFACT_DELETE_EVENTS, ARTIFACT_UPSERT_EVENTS
from harbor.helpers.utils import ObjectKind
from harbor.webhook.harbor_abstract_webhook_processor import (
    HarborAbstractWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from harbor.core.options import SingleArtifactOptions
from harbor.core.exporters.artifact_exporter import HarborArtifactExporter
from initialize_client import init_client


class ArtifactWebhookProcessor(HarborAbstractWebhookProcessor):
    """Webhook processor for Harbor artifact events."""

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the payload structure and content."""
        event_type = payload.get("type")
        if not event_type:
            return False

        valid_events = ARTIFACT_UPSERT_EVENTS + ARTIFACT_DELETE_EVENTS
        return event_type in valid_events

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ARTIFACTS]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        event_type = payload["type"]
        event_data = payload.get("event_data", {})
        resources = event_data.get("resources", [])
        repository = event_data.get("repository", {})

        if not resources or not repository:
            logger.warning(f"No resources or repository data in {event_type} event")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        logger.info(
            f"Processing artifact event: {event_type} for {len(resources)} artifacts"
        )

        if event_type in ARTIFACT_DELETE_EVENTS:
            # For delete events, return the artifacts as deleted
            deleted_artifacts = []
            for resource in resources:
                artifact_data = {
                    "project_id": repository.get("project_id"),
                    "repository_id": repository.get("repository_id"),
                    "digest": resource.get("digest"),
                    "tag": resource.get("tag"),
                    "project_name": repository.get("namespace"),
                    "repository_name": repository.get("repo_full_name"),
                }
                deleted_artifacts.append(artifact_data)

            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=deleted_artifacts
            )

        # For upsert events, fetch the latest artifact data
        client = init_client()
        exporter = HarborArtifactExporter(client)
        # Use resource_config directly without casting to avoid circular dependency

        updated_artifacts = []
        for resource in resources:
            try:
                # Extract project and repository info
                project_name = repository.get("namespace")
                repository_name = repository.get("repo_full_name")
                reference = resource.get("tag") or resource.get("digest")

                if not all([project_name, repository_name, reference]):
                    logger.warning(f"Missing required data for artifact: {resource}")
                    continue

                options = SingleArtifactOptions(
                    project_name=project_name,
                    repository_name=repository_name,
                    reference=reference,
                )

                artifact_data = await exporter.get_resource(options)
                updated_artifacts.append(artifact_data)

            except Exception as e:
                logger.error(f"Failed to fetch artifact data for {resource}: {e}")
                continue

        return WebhookEventRawResults(
            updated_raw_results=updated_artifacts, deleted_raw_results=[]
        )
