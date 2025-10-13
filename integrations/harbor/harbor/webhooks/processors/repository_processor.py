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


class RepositoryWebhookProcessor(AbstractWebhookProcessor):
    """
    Processes Harbor webhook events that affect Repositories.

    Harbor Events that affect repositories:
    - PUSH_ARTIFACT: New artifact pushed to repository
    - DELETE_ARTIFACT: Artifact deleted (may leave repo empty)
    - TAG_RETENTION: Retention policy ran on repository
    - REPLICATION: Repository replicated
    """

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """
        Check if event affects repositories.
        Most artifact events affect the repository metadata (e.g., artifact count).
        """
        event_type = event.payload.get("type", "")
        return event_type in [
            "PUSH_ARTIFACT",
            "DELETE_ARTIFACT",
            "TAG_RETENTION",
            "REPLICATION"
        ]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.REPOSITORY]

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
        Process repository webhook event.

        Harbor webhook payload structure for artifact events:
        {
            "type": "PUSH_ARTIFACT",
            "occur_at": 1234567890,
            "operator": "admin",
            "event_data": {
                "resources": [{
                    "digest": "sha256:...",
                    "tag": "latest",
                    "resource_url": "harbor.example.com/project/repo:tag"
                }],
                "repository": {
                    "name": "repo",
                    "namespace": "project",
                    "repo_full_name": "project/repo",
                    "repo_type": "public"
                }
            }
        }
        """
        client = init_harbor_client()
        event_type = payload.get("type", "")
        event_data = payload.get("event_data", {})

        # Extract repository information
        repository = event_data.get("repository", {})
        project_name = repository.get("namespace", "")
        repo_name = repository.get("name", "")
        repo_full_name = repository.get(
            "repo_full_name", f"{project_name}/{repo_name}")

        if not project_name or not repo_name:
            logger.warning(
                f"Could not extract repository info from webhook payload: {payload}")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        logger.info(
            f"Processing repository event: {event_type} for {repo_full_name}")

        # For DELETE_ARTIFACT, check if repository still exists and has artifacts
        if event_type == "DELETE_ARTIFACT":
            try:
                repo = await client.get_repository(project_name, repo_name)
                if not repo:
                    # Repository was deleted
                    logger.info(
                        f"Repository {repo_full_name} no longer exists")
                    return WebhookEventRawResults(
                        updated_raw_results=[],
                        deleted_raw_results=[
                            {"name": repo_name, "namespace": project_name}]
                    )
                elif repo.get("artifact_count", 0) == 0:
                    # Repository exists but is empty - decide if you want to keep it
                    logger.info(f"Repository {repo_full_name} is now empty")
                    return WebhookEventRawResults(
                        updated_raw_results=[repo],
                        deleted_raw_results=[]
                    )
            except Exception as e:
                logger.error(
                    f"Failed to check repository {repo_full_name}: {e}")
                return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        # For all other events, fetch updated repository data
        try:
            repo = await client.get_repository(project_name, repo_name)
            if repo:
                logger.info(
                    f"Successfully fetched updated repository: {repo_full_name}")
                return WebhookEventRawResults(
                    updated_raw_results=[repo],
                    deleted_raw_results=[]
                )
        except Exception as e:
            logger.error(f"Failed to fetch repository {repo_full_name}: {e}")

        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
