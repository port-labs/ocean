from loguru import logger
from harbor.client.client_initializer import init_harbor_client
from harbor.constants import ObjectKind
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


class ArtifactWebhookProcessor(AbstractWebhookProcessor):
    """
    Processes Harbor webhook events that affect Artifacts.

    Harbor Events:
    - PUSH_ARTIFACT: New artifact pushed
    - DELETE_ARTIFACT: Artifact deleted
    - PULL_ARTIFACT: Artifact pulled (usually don't sync on pulls)
    - SCANNING_COMPLETED: Vulnerability scan completed
    - SCANNING_FAILED: Vulnerability scan failed
    - SCANNING_STOPPED: Vulnerability scan stopped
    """

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Check if event affects artifacts"""
        event_type = event.payload.get("type", "")
        return event_type in [
            "PUSH_ARTIFACT",
            "DELETE_ARTIFACT",
            "PULL_ARTIFACT",
            "SCANNING_COMPLETED",
            "SCANNING_FAILED",
            "SCANNING_STOPPED"
        ]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ARTIFACT]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "type" in payload and "event_data" in payload

    async def handle_event(
        self,
        payload: EventPayload,
        resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """
        Process artifact webhook event.

        Harbor webhook payload structure:
        {
            "type": "PUSH_ARTIFACT",
            "occur_at": 1234567890,
            "operator": "admin",
            "event_data": {
                "resources": [{
                    "digest": "sha256:abc123...",
                    "tag": "v1.0.0",
                    "resource_url": "harbor.example.com/myproject/myrepo:v1.0.0"
                }],
                "repository": {
                    "name": "myrepo",
                    "namespace": "myproject",
                    "repo_full_name": "myproject/myrepo",
                    "repo_type": "public"
                }
            }
        }
        """
        client = init_harbor_client()
        event_type = payload.get("type", "")
        event_data = payload.get("event_data", {})

        # Extract artifact information
        resources = event_data.get("resources", [])
        if not resources:
            logger.warning("No resources found in webhook payload")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        repository = event_data.get("repository", {})
        project_name = repository.get("namespace", "")
        repo_name = repository.get("name", "")

        if not project_name or not repo_name:
            logger.warning(
                f"Could not extract repository info from payload: {payload}")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        # Process each resource (usually just one)
        updated_artifacts = []
        deleted_artifacts = []

        for resource in resources:
            digest = resource.get("digest", "")
            tag = resource.get("tag", "")

            # Use digest as the reference (more reliable than tags)
            reference = digest if digest else tag

            if not reference:
                logger.warning(
                    f"No digest or tag found in resource: {resource}")
                continue

            logger.info(
                f"Processing artifact event: {event_type} for {project_name}/{repo_name}/{reference}")

            # Handle deletion
            if event_type == "DELETE_ARTIFACT":
                logger.info(
                    f"Artifact {project_name}/{repo_name}/{reference} was deleted")
                deleted_artifacts.append({
                    "digest": digest,
                    "tag": tag,
                    "repository": repo_name,
                    "namespace": project_name
                })
                continue

            # Skip PULL_ARTIFACT if you don't want to sync on every pull
            if event_type == "PULL_ARTIFACT":
                logger.debug(f"Skipping PULL_ARTIFACT event for {reference}")
                continue

            # Fetch updated artifact data
            try:
                # For scanning events, we want to refetch the artifact to get scan results
                artifact = await client.get_artifact(project_name, repo_name, reference)
                if artifact:
                    logger.info(
                        f"Successfully fetched updated artifact: {reference}")
                    updated_artifacts.append(artifact)
                else:
                    logger.warning(
                        f"Artifact {reference} not found, may have been deleted")
                    deleted_artifacts.append({
                        "digest": digest,
                        "tag": tag,
                        "repository": repo_name,
                        "namespace": project_name
                    })
            except Exception as e:
                logger.error(f"Failed to fetch artifact {reference}: {e}")

        return WebhookEventRawResults(
            updated_raw_results=updated_artifacts,
            deleted_raw_results=deleted_artifacts
        )
