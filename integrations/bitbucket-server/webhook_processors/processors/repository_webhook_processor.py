from typing import Any

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from integration import ObjectKind
from webhook_processors.processors._bitbucket_abstract_webhook_processor import (
    BaseWebhookProcessorMixin,
)
from webhook_processors.webhook_client import REPO_WEBHOOK_EVENTS


class RepositoryWebhookProcessor(BaseWebhookProcessorMixin):
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload["eventKey"] in REPO_WEBHOOK_EVENTS

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.REPOSITORY]

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "eventKey" in payload

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        event_key = payload["eventKey"]
        deleted_raw_results = self._get_deleted_if_renamed_or_moved(payload, event_key)

        repo = (
            payload["repository"]
            if event_key == "repo:refs_changed"
            else payload["new"]
        )

        project_key = repo["project"]["key"]
        repository_slug = repo["slug"]

        logger.info(
            f"Handling repository webhook event ({event_key}) for project: {project_key} and repository: {repository_slug}"
        )

        repository = await self.client.get_single_repository(
            project_key=project_key, repo_slug=repository_slug
        )

        return WebhookEventRawResults(
            updated_raw_results=[repository],
            deleted_raw_results=deleted_raw_results,
        )

    def _get_deleted_if_renamed_or_moved(
        self, payload: EventPayload, event_key: str
    ) -> list[dict[str, Any]]:
        """Return list with old repo if slug or project key changed (rename / move)."""
        if event_key != "repo:modified":
            return []

        old = payload["old"]
        new = payload["new"]

        old_slug = old.get("slug")
        old_project = old.get("project", {}).get("key")
        new_slug = new["slug"]
        new_project = new["project"]["key"]

        if not (old_slug and old_project):
            return []

        if old_slug != new_slug or old_project != new_project:
            return [old]

        return []
