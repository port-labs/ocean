from typing import Any, cast
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from bitbucket_cloud.webhook_processors.events import RepositoryEvents
from bitbucket_cloud.helpers.utils import ObjectKind
from bitbucket_cloud.webhook_processors.processors._bitbucket_abstract_webhook_processor import (
    _BitbucketAbstractWebhookProcessor,
)
from integration import RepositoryResourceConfig
from loguru import logger


class RepositoryWebhookProcessor(_BitbucketAbstractWebhookProcessor):

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        try:
            return bool(RepositoryEvents(event.headers["x-event-key"]))
        except ValueError:
            return False

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.REPOSITORY]

    async def _enrich_with_attached_files(
        self,
        repo_data: dict[str, Any],
        file_paths: list[str],
    ) -> dict[str, Any]:
        """Enrich a repository dict with __attachedFiles."""
        repo_slug = repo_data.get("slug") or repo_data.get("name", "").replace(" ", "-")
        default_branch = repo_data.get("mainbranch", {}).get("name", "main")
        attached: dict[str, Any] = {}

        for file_path in file_paths:
            try:
                content = await self._webhook_client.get_repository_files(
                    repo_slug, default_branch, file_path
                )
                attached[file_path] = content
            except Exception as e:
                logger.debug(
                    f"Could not fetch file {file_path} from {repo_slug}@{default_branch}: {e}"
                )
                attached[file_path] = None

        repo_data["__attachedFiles"] = attached
        return repo_data

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:

        repository_id = payload["repository"]["uuid"]
        logger.info(
            f"Handling repository webhook event for repository: {repository_id}"
        )
        repository_details = await self._webhook_client.get_repository(repository_id)

        selector = cast(RepositoryResourceConfig, resource_config).selector
        attached_files = selector.attached_files or []
        if attached_files:
            repository_details = await self._enrich_with_attached_files(
                repository_details, attached_files
            )

        return WebhookEventRawResults(
            updated_raw_results=[repository_details],
            deleted_raw_results=[],
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        required_field = "repository"
        return required_field in payload
