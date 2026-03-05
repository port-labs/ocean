from loguru import logger
from port_ocean.context.ocean import ocean
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

from initialize_client import create_harbor_client
from kinds import ObjectKind


class ArtifactWebhookProcessor(AbstractWebhookProcessor):
    """Webhook processor for Harbor artifact events."""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """
        Check if this event is an artifact event.

        Harbor artifact events include:
        - harbor.artifact.pushed
        - harbor.artifact.deleted
        - harbor.artifact.pulled
        - harbor.scan.completed (assumed pattern)
        - harbor.scan.failed (assumed pattern)
        """
        event_type = event.payload.get("type", "")
        artifact_events = [
            "harbor.artifact.pushed",
            "harbor.artifact.deleted",
            "harbor.artifact.pulled",
            "harbor.scan.completed",
            "harbor.scan.failed",
        ]

        should_process = event_type in artifact_events

        if should_process:
            logger.info(f"Processing artifact webhook event: {event_type}")

        return should_process

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Return the kinds this processor handles."""
        return [ObjectKind.ARTIFACT]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """Authenticate the webhook request."""
        return headers.get("authorization") == ocean.integration_config.get(
            "webhook_secret"
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the webhook payload has required fields."""
        required_fields = ["type", "data"]

        if not all(field in payload for field in required_fields):
            logger.warning(f"Webhook payload missing required fields: {payload}")
            return False

        data = payload.get("data", {})
        if "resources" not in data or "repository" not in data:
            logger.warning(f"Webhook data missing resources or repository: {data}")
            return False

        return True

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig | None
    ) -> WebhookEventRawResults:
        """
        Handle artifact webhook event.

        Payload structure:
        {
            "type": "harbor.artifact.pushed",
            "data": {
                "resources": [
                    {
                        "digest": "sha256:...",
                        "tag": "v1",
                        "resource_url": "host/project/repo:tag"
                    }
                ],
                "repository": {
                    "name": "redis",
                    "namespace": "ocean-integration",
                    "repo_full_name": "ocean-integration/redis",
                    "repo_type": "public"
                }
            }
        }

        Args:
            payload: The webhook payload
            resource_config: Resource configuration

        Returns:
            WebhookEventRawResults with updated or deleted artifacts
        """
        event_type = payload.get("type")
        data = payload.get("data", {})
        resources = data.get("resources", [])
        repository = data.get("repository", {})

        logger.info(f"Handling {event_type} event for {len(resources)} resources")

        # Extract project and repository names from repository object
        project_name = repository.get("namespace", "")
        repo_name = repository.get("name", "")
        repo_full_name = repository.get("repo_full_name", "")

        if not project_name or not repo_name:
            logger.warning(
                f"Could not extract project/repo names from repository: {repository}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        logger.info(f"Processing artifacts for {project_name}/{repo_name}")

        client = create_harbor_client()
        updated_artifacts = []
        deleted_artifacts = []

        for resource in resources:
            digest = resource.get("digest", "")
            tag = resource.get("tag", "")

            if not digest:
                logger.warning(f"Artifact resource missing digest: {resource}")
                continue

            logger.info(f"Processing artifact: digest={digest}, tag={tag}")

            if event_type == "harbor.artifact.deleted":
                # For deletion, we need to construct a minimal artifact object
                # to identify what to delete in Port
                deleted_artifact = {
                    "digest": digest,
                    "tags": [{"name": tag}] if tag and tag != digest else [],
                    "_project_name": project_name,
                    "_repository_name": repo_name,
                    "_repository_full_name": repo_full_name,
                }
                deleted_artifacts.append(deleted_artifact)
                logger.info(f"Marked artifact for deletion: {digest}")
            if event_type == "harbor.artifact.pulled":
                pass
            else:
                # For push/pull/scan events, fetch fresh data from Harbor
                try:
                    # Use digest as reference
                    reference = digest

                    artifact_data = await client.get_artifact(
                        project_name=project_name,
                        repository_name=repo_name,
                        reference=reference,
                        params={
                            "with_tag": True,
                            "with_scan_overview": True,
                            "with_label": True,
                        },
                    )

                    # Enrich with context
                    artifact_data["_project_name"] = project_name
                    artifact_data["_repository_name"] = repo_name
                    artifact_data["_repository_full_name"] = repo_full_name

                    updated_artifacts.append(artifact_data)
                    logger.info(f"Fetched fresh artifact data for: {digest}")
                except Exception as e:
                    logger.error(
                        f"Failed to fetch artifact {project_name}/{repo_name}@{digest}: {e}"
                    )
                    # If we can't fetch it, we might want to still report what we know from the webhook
                    logger.warning(f"Using webhook data as fallback for {digest}")

        logger.info(
            f"Webhook processing complete: "
            f"{len(updated_artifacts)} updated, {len(deleted_artifacts)} deleted"
        )

        return WebhookEventRawResults(
            updated_raw_results=updated_artifacts,
            deleted_raw_results=deleted_artifacts,
        )
